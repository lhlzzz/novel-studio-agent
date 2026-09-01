"""Distribution agent owns gated external actions through ProviderResolver."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
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
    IntegrationAccount,
    transition_job,
    make_idempotency_key,
)
from integrations.distribution_service import DistributionService
from integrations.persistence import InMemoryStore, JobStore
from integrations.providers.resolver import resolve_adapter, resolve_capability, resolve_provider
from integrations.registry.loader import load_registry


class DistributionAgent:
    """Select providers, create jobs, and delegate gated execution."""

    name = "distribution-agent"
    owner = "distribution"
    capabilities = (
        "list_accounts",
        "list_integrations",
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
        accounts_path: Path | None = None,
        store: JobStore | None = None,
        provider_name: str = "postiz",
    ) -> None:
        self.registry = registry or load_registry()
        self.provider_name = provider_name
        self.adapter = adapter or resolve_adapter(self.provider_name, adapter=resolve_provider(self.provider_name).implementation)
        self.accounts_path = accounts_path or Path(__file__).resolve().parents[1] / "config/postiz/integrations.yaml"
        self.store = store or InMemoryStore()
        self.service = DistributionService(self.adapter, store=self.store)

    def list_accounts(self) -> list[IntegrationAccount]:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("PyYAML is required to load provider accounts") from exc
        raw = yaml.safe_load(self.accounts_path.read_text(encoding="utf-8")) or {}
        provider = str(raw.get("provider") or self.provider_name)
        accounts = []
        for item in raw.get("accounts") or []:
            platform = str(item.get("platform") or "").strip()
            if platform:
                accounts.append(
                    IntegrationAccount(
                        platform=platform,
                        integration_id=str(item.get("integration_id") or "").strip(),
                        status=str(item.get("status") or "pending"),
                        provider=provider,
                        account_name=str(item.get("account_name") or ""),
                        account_id=str(item.get("account_id") or "").strip(),
                        capabilities=tuple(item.get("capabilities") or ()),
                        verified_at=item.get("verified_at"),
                        enabled=bool(item.get("enabled") and item.get("verified")),
                    )
                )
        return accounts

    def list_integrations(self):
        return self.adapter.list_integrations()

    def get_capabilities(self, integration_id: str):
        return resolve_capability(integration_id, "publish", adapter=self.adapter)

    def select_provider(self, platform: str) -> IntegrationAccount:
        configured = next((item for item in self.list_accounts() if item.platform == platform), None)
        if configured is None or configured.status != "active":
            raise RuntimeError(f"provider is not runtime verified: no active verified account for platform={platform}")
        authenticate = getattr(self.adapter, "authenticate", None)
        if not callable(authenticate) or not authenticate():
            raise RuntimeError("provider is not runtime verified")
        list_integrations = getattr(self.adapter, "list_integrations", None)
        if not callable(list_integrations):
            raise RuntimeError("provider is not runtime verified: account discovery unavailable")
        for integration in list_integrations():
            integration_platform = getattr(integration, "platform", "") or getattr(integration, "provider", "")
            if integration_platform != platform:
                continue
            if configured.integration_id and configured.integration_id != integration.id:
                continue
            verify = getattr(self.adapter, "verify_capabilities", None)
            capabilities = verify(integration.id) if callable(verify) else self.adapter.get_capabilities(integration.id)
            record = (getattr(capabilities, "records", {}) or {}).get("publish")
            if record is None or not record.allowed:
                continue
            runtime = replace(integration, enabled=True, state="ENABLED", capabilities=capabilities)
            self.store.save_integration(runtime)
            return IntegrationAccount(
                platform=platform,
                integration_id=runtime.id,
                status="active",
                provider=runtime.provider,
                account_name=runtime.account_name,
                account_id=getattr(runtime, "account_id", "") or "",
                capabilities=tuple((getattr(capabilities, "records", {}) or {})),
                verified_at=getattr(runtime, "verified_at", None),
                enabled=True,
            )
        raise RuntimeError(f"no active verified account for platform={platform}")

    def _variant(self, package: ContentPackage, integration_id: str, platform: str):
        return build_variant(package, integration_id=integration_id, platform=platform)

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
            integration_id=account.integration_id,
            variant=self._variant(package, account.integration_id, platform),
            action=action,
            scheduled_at=scheduled_at,
            status="DRAFT",
            idempotency_key=make_idempotency_key(package.package_id, account.integration_id, action, scheduled_at),
            brand_id=package.brand_id,
            creator_id=package.creator_id,
            campaign_id=package.campaign_id,
            request_id=request_id or new_request_id(),
        )
        self.store.save_content_package(package)
        integration = self.adapter.get_integration(account.integration_id)
        self.store.save_integration(replace(integration, enabled=True, state="ENABLED"))
        return self.store.save_job(job)

    def validate(self, job: DistributionJob) -> list[str]:
        return self.adapter.validate_payload(job)

    def dry_run(self, job: DistributionJob) -> dict[str, Any]:
        return self.service.dry_run(job)

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
        capability_verified: bool = False,
        idempotency_valid: bool = False,
        media_uploaded: bool = False,
        payload_valid: bool = False,
    ):
        integration = self.adapter.get_integration(job.integration_id)
        capability = resolve_capability(
            job.integration_id,
            "schedule" if job.action == "schedule" else "publish",
            adapter=self.adapter,
        )

        def gate_check(candidate: DistributionJob) -> bool:
            return not check_distribution_job(
                candidate,
                integration,
                content_valid=content_valid,
                evidence_valid=evidence_valid,
                account_valid=account_valid,
                media_valid=media_valid,
                approval_valid=approval_valid,
                provider_verified=provider_verified or bool(integration.enabled),
                integration_verified=integration_verified or integration.state in {"VERIFIED", "ENABLED"},
                capability_verified=capability_verified or capability.allowed,
                idempotency_valid=idempotency_valid or bool(candidate.idempotency_key),
                media_uploaded=media_uploaded or not candidate.variant.media or bool((candidate.variant.metadata or {}).get("uploaded_media")),
                payload_valid=payload_valid or not self.adapter.validate_payload(candidate),
            )

        return self.service.execute(job, gate_check=gate_check)

    def schedule(self, job: DistributionJob, **gate: bool):
        scheduled = replace(job, action="schedule") if job.action != "schedule" else job
        return self.execute(scheduled, **gate)

    def status(self, job_id: str) -> dict[str, Any]:
        publication = self.store.get_publication(job_id)
        if publication is None:
            return {"id": job_id, "status": "UNKNOWN"}
        return self.adapter.get_status(publication.resolved_provider_post_id())

    def cancel(self, job_id: str) -> DistributionJob:
        job = self.store.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        cancelled = transition_job(job, "CANCELLED")
        publication = self.store.get_publication(job_id)
        if publication is not None:
            cancel = getattr(self.adapter, "cancel", None) or getattr(self.adapter, "delete", None)
            if callable(cancel):
                cancel(publication.resolved_provider_post_id())
        return self.store.save_job(cancelled)

    def reconcile(self, job_id: str) -> dict[str, Any]:
        from services.reconciliation.service import reconcile_distribution_job

        return reconcile_distribution_job(job_id, adapter=self.adapter, store=self.store)

    def sync_analytics(
        self,
        *,
        publication_id: str,
        post_id: str,
        platform: str,
    ) -> NormalizedMetrics:
        raw = self.adapter.get_analytics(post_id)
        metrics = normalize_metrics(
            publication_id,
            raw,
            platform=platform,
            post_id=post_id,
        )
        persist_metrics(metrics)
        return metrics
