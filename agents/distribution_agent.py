"""Distribution agent owns gated external actions through SocialProviderResolver."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from analytics.normalizers.metrics import NormalizedMetrics, normalize_metrics
from analytics.persistence import persist_metrics
from content.models import ContentPackage
from governance.distribution_gate import admit_distribution_job
from social.variants import build_platform_variant
from governance.observability import new_request_id
from integrations.contracts.distribution import (
    DistributionJob,
    Integration,
    transition_job,
    make_idempotency_key,
)
from integrations.distribution_service import DistributionService
from integrations.persistence import InMemoryStore, JobStore
from social.accounts.manager import SocialAccountManager
from social.accounts.models import SocialAccount
from social.providers.resolver import resolve_adapter, resolve_capability, resolve_social_provider


class DistributionAgent:
    """Select accounts, create jobs, and delegate gated execution. Never call platform HTTP."""

    name = "distribution-agent"
    owner = "distribution"
    capabilities = (
        "list_accounts",
        "get_account",
        "get_capabilities",
        "create_job",
        "dry_run",
        "validate",
        "execute",
        "schedule",
        "status",
        "cancel",
        "reconcile",
        "sync_analytics",
    )

    def __init__(
        self,
        *,
        adapter: Any | None = None,
        registry: dict[str, Integration] | None = None,
        store: JobStore | None = None,
        manager: SocialAccountManager | None = None,
        provider_name: str | None = None,
        secrets: Any | None = None,
    ) -> None:
        self.store = store or InMemoryStore()
        self.registry = registry or {}
        self.adapter = adapter
        self.provider_name = provider_name
        self.secrets = secrets
        self.manager = manager or SocialAccountManager(store=self.store, secrets=secrets)
        if adapter is not None:
            self.service = DistributionService(adapter, store=self.store)
        else:
            self.service = None

    def _adapter_for(self, provider: str) -> Any:
        if self.adapter is not None:
            return self.adapter
        return resolve_social_provider(provider).implementation

    def _service(self, adapter: Any) -> DistributionService:
        if self.adapter is not None and self.service is not None:
            return self.service
        return DistributionService(adapter, store=self.store)

    def list_accounts(self) -> list[SocialAccount]:
        stored = self.manager.list_accounts()
        if stored:
            return stored
        if self.adapter is not None and hasattr(self.adapter, "list_accounts"):
            return list(self.adapter.list_accounts())
        return []

    def list_integrations(self):
        adapter = self.adapter
        if adapter is None:
            return [item.as_integration() for item in self.list_accounts()]
        return adapter.list_integrations()

    def get_capabilities(self, account_id: str):
        adapter = self.adapter or self._adapter_for(self.provider_name or "douyin")
        return resolve_capability(account_id, "publish", adapter=adapter)

    def select_provider(self, platform: str) -> SocialAccount:
        if self.adapter is not None:
            authenticate = getattr(self.adapter, "authenticate", None)
            if callable(authenticate) and not authenticate():
                raise RuntimeError("provider is not runtime verified")
            list_accounts = getattr(self.adapter, "list_accounts", None)
            accounts = list(list_accounts()) if callable(list_accounts) else []
            for account in accounts:
                if getattr(account, "platform", "") != platform and getattr(account, "provider", "") != platform:
                    continue
                status = getattr(account, "status", None) or getattr(account, "state", "")
                if status not in {"VERIFIED", "ENABLED"} and not getattr(account, "enabled", False):
                    continue
                verify = getattr(self.adapter, "verify_capabilities", None)
                capabilities = verify(account.account_id) if callable(verify) else getattr(account, "capabilities", None)
                if capabilities is not None and hasattr(account, "capabilities"):
                    account = replace(account, capabilities=capabilities) if hasattr(account, "capabilities") else account
                if getattr(account, "status", "") != "ENABLED":
                    continue
                self.store.save_account(account)
                return account
            raise RuntimeError(f"no active verified account for platform={platform}")
        try:
            return self.manager.select_enabled(platform, account_id=None, provider=self.provider_name)
        except Exception as exc:
            raise RuntimeError(f"provider is not runtime verified: no active verified account for platform={platform}") from exc

    def _variant(self, package: ContentPackage, account_id: str, platform: str):
        built = build_platform_variant(package, account_id=account_id, platform=platform)
        return built.variant

    def create_job(
        self,
        package: ContentPackage,
        *,
        platform: str,
        job_id: str,
        scheduled_at: str | None = None,
        request_id: str | None = None,
        account_id: str | None = None,
    ) -> DistributionJob:
        if account_id:
            account = self.manager.get_account(account_id)
            if account.status != "ENABLED":
                raise RuntimeError(f"account {account_id} is not ENABLED")
        else:
            account = self.select_provider(platform)
        action = "publish"
        job = DistributionJob(
            job_id=job_id,
            content_package_id=package.package_id,
            account_id=account.account_id,
            variant=self._variant(package, account.account_id, platform),
            action=action,
            scheduled_at=scheduled_at,
            status="SCHEDULED" if scheduled_at else "DRAFT",
            idempotency_key=make_idempotency_key(package.package_id, account.account_id, action, scheduled_at),
            brand_id=package.brand_id,
            creator_id=package.creator_id,
            campaign_id=package.campaign_id,
            request_id=request_id or new_request_id(),
        )
        self.store.save_content_package(package)
        self.store.save_account(account)
        return self.store.save_job(job)

    def validate(self, job: DistributionJob) -> list[str]:
        adapter = self._adapter_for(self.provider_name or "douyin")
        return adapter.validate_payload(job)

    def dry_run(self, job: DistributionJob) -> dict[str, Any]:
        adapter = self.adapter or self._adapter_for(self.provider_name or "douyin")
        return self._service(adapter).dry_run(job)

    def execute(self, job: DistributionJob, **_ignored: Any):
        platform = self.provider_name or ((job.variant.metadata or {}).get("platform") if job.variant.metadata else None) or "douyin"
        adapter = self.adapter or self._adapter_for(platform)

        def gate_check(candidate: DistributionJob) -> bool:
            decision = admit_distribution_job(candidate, adapter=adapter, store=self.store)
            return decision.ready

        publishable = job if job.action in {"publish", "scheduled_publish"} else replace(job, action="publish")
        return self._service(adapter).execute(publishable, gate_check=gate_check)

    def schedule(self, job: DistributionJob, **_ignored: Any):
        from integrations.contracts.distribution import transition_job
        scheduled = replace(job, action="publish", status=job.status)
        if scheduled.status == "DRAFT":
            scheduled = transition_job(scheduled, "SCHEDULED", action="publish")
        elif scheduled.status != "SCHEDULED":
            scheduled = replace(scheduled, status="SCHEDULED")
        return self.store.save_job(scheduled)

    def status(self, job_id: str) -> dict[str, Any]:
        publication = self.store.get_publication(job_id)
        if publication is None:
            return {"id": job_id, "status": "UNKNOWN"}
        adapter = self.adapter or self._adapter_for(publication.provider)
        return adapter.get_status(publication.resolved_provider_post_id())

    def cancel(self, job_id: str) -> DistributionJob:
        job = self.store.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        cancelled = transition_job(job, "CANCELLED")
        publication = self.store.get_publication(job_id)
        if publication is not None:
            adapter = self.adapter or self._adapter_for(publication.provider)
            cancel = getattr(adapter, "cancel", None) or getattr(adapter, "delete", None)
            if callable(cancel):
                cancel(publication.resolved_provider_post_id())
        return self.store.save_job(cancelled)

    def reconcile(self, job_id: str) -> dict[str, Any]:
        from social.reconciliation.service import reconcile_distribution_job

        adapter = self.adapter or self._adapter_for(self.provider_name or "douyin")
        return reconcile_distribution_job(job_id, adapter=adapter, store=self.store)

    def sync_analytics(
        self,
        *,
        publication_id: str,
        post_id: str,
        platform: str,
    ) -> NormalizedMetrics:
        adapter = self.adapter or self._adapter_for(platform)
        if hasattr(adapter, "analytics"):
            from integrations.contracts.distribution import Publication

            raw = adapter.analytics(Publication(publication_id, "", platform, post_id, platform=platform))
        else:
            raw = adapter.get_analytics(post_id)
        metrics = normalize_metrics(
            publication_id,
            raw,
            platform=platform,
            post_id=post_id,
        )
        persist_metrics(metrics)
        return metrics
