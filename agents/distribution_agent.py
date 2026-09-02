"""Distribution agent owns gated external actions through SocialProviderResolver."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from analytics.normalizers.metrics import NormalizedMetrics, normalize_metrics
from analytics.persistence import persist_metrics
from content.models import ContentPackage
from content.variants import build_variant
from governance.distribution_gate import check_distribution_job
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
    ) -> None:
        self.store = store or InMemoryStore()
        self.registry = registry or {}
        self.adapter = adapter
        self.provider_name = provider_name
        self.manager = manager or SocialAccountManager(store=self.store)
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
        adapter = self.adapter or self._adapter_for(self.provider_name or "x")
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
                if getattr(account, "status", "") == "VERIFIED":
                    account = replace(account, status="ENABLED")
                self.store.save_account(account)
                return account
            list_integrations = getattr(self.adapter, "list_integrations", None)
            if callable(list_integrations):
                for integration in list_integrations():
                    integration_platform = getattr(integration, "platform", "") or getattr(integration, "provider", "")
                    if integration_platform != platform:
                        continue
                    verify = getattr(self.adapter, "verify_capabilities", None)
                    capabilities = verify(integration.id) if callable(verify) else self.adapter.get_capabilities(integration.id)
                    record = (getattr(capabilities, "records", {}) or {}).get("publish")
                    if record is None or not record.allowed:
                        continue
                    account = SocialAccount(
                        account_id=integration.id,
                        provider=integration.provider,
                        platform=platform,
                        username=getattr(integration, "account_name", "") or "",
                        display_name=getattr(integration, "account_name", "") or "",
                        status="ENABLED",
                        last_verified_at=getattr(integration, "verified_at", None),
                    )
                    self.store.save_account(account)
                    self.store.save_integration(replace(integration, enabled=True, state="ENABLED", capabilities=capabilities))
                    return account
            raise RuntimeError(f"no active verified account for platform={platform}")
        try:
            return self.manager.select_verified(platform)
        except Exception as exc:
            raise RuntimeError(f"provider is not runtime verified: no active verified account for platform={platform}") from exc

    def _variant(self, package: ContentPackage, account_id: str, platform: str):
        return build_variant(package, account_id=account_id, platform=platform)

    def create_job(
        self,
        package: ContentPackage,
        *,
        platform: str,
        job_id: str,
        scheduled_at: str | None = None,
        request_id: str | None = None,
    ) -> DistributionJob:
        account = self.select_provider(platform)
        action = "schedule" if scheduled_at else "publish"
        job = DistributionJob(
            job_id=job_id,
            content_package_id=package.package_id,
            account_id=account.account_id,
            variant=self._variant(package, account.account_id, platform),
            action=action,
            scheduled_at=scheduled_at,
            status="DRAFT",
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
        adapter = self._adapter_for(self.provider_name or "x")
        return adapter.validate_payload(job)

    def dry_run(self, job: DistributionJob) -> dict[str, Any]:
        adapter = self.adapter or self._adapter_for(self.provider_name or "x")
        return self._service(adapter).dry_run(job)

    def execute(
        self,
        job: DistributionJob,
        *,
        content_valid: bool,
        evidence_valid: bool,
        account_valid: bool,
        media_valid: bool,
        approval_valid: bool,
        provider_verified: bool = False,
        integration_verified: bool = False,
        account_verified: bool = False,
        capability_verified: bool = False,
        idempotency_valid: bool = False,
        media_uploaded: bool = False,
        payload_valid: bool = False,
    ):
        adapter = self.adapter or self._adapter_for(self.provider_name or "x")
        account = adapter.get_account(job.account_id) if hasattr(adapter, "get_account") else adapter.get_integration(job.account_id)
        capability = resolve_capability(
            job.account_id,
            "schedule" if job.action == "schedule" else "publish",
            adapter=adapter,
        )

        def gate_check(candidate: DistributionJob) -> bool:
            return not check_distribution_job(
                candidate,
                account,
                content_valid=content_valid,
                evidence_valid=evidence_valid,
                account_valid=account_valid,
                media_valid=media_valid,
                approval_valid=approval_valid,
                provider_verified=provider_verified or bool(getattr(account, "enabled", False)),
                integration_verified=integration_verified or getattr(account, "status", getattr(account, "state", "")) in {"VERIFIED", "ENABLED"},
                account_verified=account_verified or getattr(account, "verified", False) or getattr(account, "status", "") in {"VERIFIED", "ENABLED"},
                capability_verified=capability_verified or capability.allowed,
                idempotency_valid=idempotency_valid or bool(candidate.idempotency_key),
                media_uploaded=media_uploaded or not candidate.variant.media or bool((candidate.variant.metadata or {}).get("uploaded_media")),
                payload_valid=payload_valid or not adapter.validate_payload(candidate),
            )

        return self._service(adapter).execute(job, gate_check=gate_check)

    def schedule(self, job: DistributionJob, **gate: bool):
        scheduled = replace(job, action="schedule") if job.action != "schedule" else job
        return self.execute(scheduled, **gate)

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

        adapter = self.adapter or self._adapter_for(self.provider_name or "x")
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
