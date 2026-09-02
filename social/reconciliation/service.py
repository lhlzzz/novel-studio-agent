"""Reconcile DistributionJob, Publication, and remote posts through native providers."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from integrations.contracts.distribution import Publication, transition_job
from integrations.persistence import InMemoryStore, JobStore

STATUS_MAP = {
    "published": "PUBLISHED",
    "ok": "PUBLISHED",
    "success": "PUBLISHED",
    "online": "PUBLISHED",
    "scheduled": "SCHEDULED",
    "queue": "SUBMITTED",
    "queued": "SUBMITTED",
    "pending": "SUBMITTED",
    "processing": "PUBLISHING",
    "reviewing": "PUBLISHING",
    "submitted": "SUBMITTED",
    "handoff_required": "SUBMITTED",
    "ready_for_xhs": "SUBMITTED",
    "not_published": "SUBMITTED",
    "offline": "FAILED",
    "blocked": "FAILED",
    "failed": "FAILED",
    "error": "FAILED",
    "canceled": "CANCELLED",
    "cancelled": "CANCELLED",
    "deleted": "CANCELLED",
    "unknown": "UNKNOWN",
    "missing": "UNKNOWN",
}


def _mapped(raw: str) -> str:
    return STATUS_MAP.get(str(raw or "").lower(), "UNKNOWN")


class SocialReconciliationService:
    def __init__(self, adapter: Any, store: JobStore | None = None) -> None:
        self.adapter = adapter
        self.store = store or InMemoryStore()

    def reconcile(self, job_id: str) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        publication = self.store.get_publication(job_id)
        if publication is None:
            return {"job_id": job_id, "status": "UNKNOWN", "reason": "publication missing"}
        raw = self.adapter.get_status(publication.resolved_provider_post_id())
        updated = self.reconcile_publication(publication, raw if isinstance(raw, dict) else {})
        self.store.save_publication(updated)
        if job is not None and job.status != updated.status:
            target = updated.status
            if job.status not in {"RECONCILING"} and "RECONCILING" in __import__("integrations.contracts.distribution", fromlist=["JOB_TRANSITIONS"]).JOB_TRANSITIONS.get(job.status, set()):
                job = self.store.save_job(transition_job(job, "RECONCILING"))
            try:
                job = transition_job(job, target)
                self.store.save_job(job)
            except Exception:
                if job.status != "RECONCILING":
                    raise
                job = transition_job(job, "UNKNOWN" if target not in {"PUBLISHED", "FAILED", "CANCELLED", "SUBMITTED", "SCHEDULED", "PUBLISHING"} else target)
                self.store.save_job(job)
        return {
            "job_id": job_id,
            "distribution_job_id": job_id,
            "provider_post_id": updated.resolved_provider_post_id(),
            "platform_object_id": updated.resolved_platform_object_id(),
            "status": updated.status,
            "raw": raw,
        }

    @staticmethod
    def reconcile_publication(publication: Publication, raw: dict[str, Any]) -> Publication:
        status = _mapped(str(raw.get("status") or raw.get("state") or "unknown"))
        platform_object_id = raw.get("platform_object_id") or raw.get("external_id") or raw.get("externalId") or publication.platform_object_id
        return replace(
            publication,
            status=status,
            platform_object_id=str(platform_object_id) if platform_object_id is not None else publication.platform_object_id,
            published_at=raw.get("published_at") or raw.get("publishedDate") or publication.published_at,
        )


def reconcile_publication(publication: Publication, raw: dict[str, Any]) -> Publication:
    return SocialReconciliationService.reconcile_publication(publication, raw)


def reconcile_distribution_job(job_id: str, *, adapter: Any, store: JobStore | None = None) -> dict[str, Any]:
    return SocialReconciliationService(adapter, store=store).reconcile(job_id)
