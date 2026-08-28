"""Meiti-owned orchestration around a verified distribution adapter."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from integrations.contracts.distribution import DistributionAdapter, DistributionJob, Publication


class ExternalActionBlocked(RuntimeError):
    """Raised when a distribution job cannot safely leave Meiti."""


class DistributionService:
    def __init__(self, adapter: DistributionAdapter) -> None:
        self.adapter = adapter

    def dry_run(self, job: DistributionJob) -> dict[str, Any]:
        integration = self.adapter.get_integration(job.integration_id)
        settings = self.adapter.get_settings(job.integration_id)
        errors = self.adapter.validate_payload(job)
        return {
            "status": "BLOCKED" if errors else "READY",
            "integration_id": integration.id,
            "settings": settings,
            "errors": errors,
            "job": asdict(job),
        }

    def execute(
        self,
        job: DistributionJob,
        *,
        gate_check: Callable[[DistributionJob], bool],
    ) -> Publication:
        dry_run = self.dry_run(job)
        if dry_run["status"] != "READY":
            raise ExternalActionBlocked("distribution payload or capability is invalid")
        if not gate_check(job):
            raise ExternalActionBlocked("publish gate is not approved")
        result = self.adapter.schedule(job) if job.action == "schedule" else self.adapter.publish(job)
        post_id = str(result.get("id") or result.get("postId") or result.get("post_id") or "")
        if not post_id:
            raise ExternalActionBlocked("Postiz response did not contain an external post id")
        integration = self.adapter.get_integration(job.integration_id)
        return Publication(
            distribution_job_id=job.job_id,
            postiz_post_id=post_id,
            integration_id=integration.id,
            provider=integration.provider,
            status=str(result.get("status") or "submitted"),
            published_at=result.get("published_at"),
            external_id=(
                str(result["external_id"])
                if result.get("external_id") is not None
                else (str(result["externalId"]) if result.get("externalId") is not None else None)
            ),
        )
