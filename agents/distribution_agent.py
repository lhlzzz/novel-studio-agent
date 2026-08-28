"""Meiti-owned distribution orchestration through a verified provider."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from content.models import ContentPackage
from analytics.normalizers.metrics import NormalizedMetrics, normalize_metrics
from analytics.persistence import persist_metrics
from governance.distribution_gate import check_distribution_job
from integrations.contracts.distribution import DistributionJob, Integration
from integrations.distribution_service import DistributionService
from integrations.providers.postiz.adapter import PostizAdapter
from integrations.registry.loader import load_registry


@dataclass(frozen=True)
class ProviderAccount:
    platform: str
    integration_id: str
    status: str


class DistributionAgent:
    """Select providers, create jobs, and delegate gated execution."""

    def __init__(
        self,
        *,
        adapter: PostizAdapter | None = None,
        registry: dict[str, Integration] | None = None,
        accounts_path: Path | None = None,
    ) -> None:
        self.adapter = adapter or PostizAdapter()
        self.registry = registry or load_registry()
        self.accounts_path = accounts_path or Path(__file__).resolve().parents[1] / "config/postiz/integrations.yaml"

    def list_accounts(self) -> list[ProviderAccount]:
        """Return only configured, non-empty account mappings."""

        try:
            import yaml
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("PyYAML is required to load Postiz accounts") from exc
        raw = yaml.safe_load(self.accounts_path.read_text(encoding="utf-8")) or {}
        if raw.get("provider") != "postiz":
            raise ValueError("Postiz account config has an unexpected provider")
        accounts = []
        for item in raw.get("accounts") or []:
            integration_id = str(item.get("integration_id") or "").strip()
            if integration_id:
                accounts.append(
                    ProviderAccount(
                        platform=str(item.get("platform") or ""),
                        integration_id=integration_id,
                        status=str(item.get("status") or "pending"),
                    )
                )
        return accounts

    def select_provider(self, platform: str) -> ProviderAccount:
        provider = self.registry.get("postiz")
        if provider is None or not provider.enabled:
            raise RuntimeError("Postiz provider is not runtime verified")
        for account in self.list_accounts():
            if account.platform == platform and account.status == "active":
                return account
        raise RuntimeError(f"no active verified Postiz account for platform={platform}")

    def create_job(
        self,
        package: ContentPackage,
        *,
        platform: str,
        job_id: str,
        scheduled_at: str | None = None,
    ) -> DistributionJob:
        account = self.select_provider(platform)
        return DistributionJob(
            job_id=job_id,
            content_package_id=package.package_id,
            integration_id=account.integration_id,
            variant=self._variant(package, account.integration_id),
            action="schedule" if scheduled_at else "publish",
            scheduled_at=scheduled_at,
        )

    @staticmethod
    def _variant(package: ContentPackage, integration_id: str):
        from integrations.contracts.distribution import ContentVariant

        return ContentVariant(
            integration_id=integration_id,
            body=package.body,
            media=tuple(package.metadata.get("media", ())),
            metadata=package.metadata,
        )

    def execute(
        self,
        job: DistributionJob,
        *,
        content_valid: bool,
        evidence_valid: bool,
        account_valid: bool,
        media_valid: bool,
        approval_valid: bool,
    ):
        integration = self.adapter.get_integration(job.integration_id)

        def gate_check(candidate: DistributionJob) -> bool:
            return not check_distribution_job(
                candidate,
                integration,
                content_valid=content_valid,
                evidence_valid=evidence_valid,
                account_valid=account_valid,
                media_valid=media_valid,
                approval_valid=approval_valid,
            )

        return DistributionService(self.adapter).execute(job, gate_check=gate_check)

    def status(self, job_id: str) -> dict[str, Any]:
        return self.adapter.get_status(job_id)

    def sync_analytics(
        self,
        *,
        publication_id: str,
        post_id: str,
        platform: str,
    ) -> NormalizedMetrics:
        """Pull provider metrics and persist the normalized Meiti record."""

        raw = self.adapter.get_analytics(post_id)
        metrics = normalize_metrics(
            publication_id,
            raw,
            platform=platform,
            post_id=post_id,
        )
        persist_metrics(metrics)
        return metrics
