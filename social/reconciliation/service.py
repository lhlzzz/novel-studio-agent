"""Reconcile DistributionJob, Publication, and remote posts through native providers.

XHS handoff is not a remote publication and never enters this path.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from integrations.contracts.distribution import IllegalJobTransition, Publication, transition_job
from integrations.persistence import JobStore

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
    def __init__(self, adapter: Any, store: JobStore) -> None:
        if store is None:
            raise ValueError("SocialReconciliationService requires an explicit store")
        self.adapter = adapter
        self.store = store

    def reconcile(self, job_id: str) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        getter = getattr(self.store, "get_handoff_by_job", None)
        handoff = getter(job_id) if callable(getter) else None
        if handoff is not None:
            return {
                "job_id": job_id,
                "status": "NOT_APPLICABLE",
                "reason": "XHS handoff is not a remote publication",
                "handoff_id": handoff.handoff_id,
                "handoff_status": handoff.status,
            }
        publication = self.store.get_publication(job_id)
        if publication is None:
            return {"job_id": job_id, "status": "UNKNOWN", "reason": "publication missing"}
        raw = self.adapter.get_status(publication.resolved_provider_post_id())
        updated = self.reconcile_publication(publication, raw if isinstance(raw, dict) else {})
        self.store.save_publication(updated)
        if job is not None and job.status != updated.status:
            target = updated.status
            transitions = __import__("integrations.contracts.distribution", fromlist=["JOB_TRANSITIONS"]).JOB_TRANSITIONS
            if job.status not in {"RECONCILING"} and "RECONCILING" in transitions.get(job.status, set()):
                job = self.store.save_job(transition_job(job, "RECONCILING"))
            try:
                job = transition_job(job, target)
                self.store.save_job(job)
            except IllegalJobTransition:
                if job.status != "RECONCILING":
                    raise
                fallback = target if target in {"PUBLISHED", "FAILED", "CANCELLED", "SUBMITTED", "SCHEDULED", "PUBLISHING"} else "UNKNOWN"
                job = transition_job(job, fallback)
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
        object_type = str(raw.get("provider_object_type") or publication.provider_object_type or "")
        return replace(
            publication,
            status=status,
            platform_object_id=str(platform_object_id) if platform_object_id is not None else publication.platform_object_id,
            published_at=raw.get("published_at") or raw.get("publishedDate") or publication.published_at,
            provider_object_type=object_type,
        )


def reconcile_publication(publication: Publication, raw: dict[str, Any]) -> Publication:
    return SocialReconciliationService.reconcile_publication(publication, raw)


def reconcile_distribution_job(job_id: str, *, adapter: Any, store: JobStore) -> dict[str, Any]:
    if store is None:
        raise ValueError("reconciliation requires an explicit store")
    return SocialReconciliationService(adapter, store=store).reconcile(job_id)
