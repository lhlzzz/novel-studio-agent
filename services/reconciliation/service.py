"""Reconcile Meiti jobs and publications against provider status."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from integrations.contracts.distribution import Publication, transition_job
from integrations.persistence import InMemoryStore, JobStore

STATUS_MAP = {
    "published": "PUBLISHED",
    "ok": "PUBLISHED",
    "success": "PUBLISHED",
    "scheduled": "SCHEDULED",
    "queue": "SCHEDULED",
    "queued": "SCHEDULED",
    "pending": "SCHEDULED",
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


def reconcile_provider_status(raw: dict[str, Any]) -> str:
    return _mapped(str(raw.get("status") or raw.get("state") or "unknown"))


def reconcile_publication(publication: Publication, raw: dict[str, Any]) -> Publication:
    status = reconcile_provider_status(raw)
    platform_object_id = raw.get("platformPostId") or raw.get("releaseId") or raw.get("externalId") or raw.get("external_id") or publication.platform_object_id
    return replace(
        publication,
        status=status,
        platform_object_id=str(platform_object_id) if platform_object_id is not None else publication.platform_object_id,
        published_at=raw.get("publishedDate") or raw.get("published_at") or publication.published_at,
    )


def reconcile_distribution_job(job_id: str, *, adapter: Any, store: JobStore | None = None) -> dict[str, Any]:
    store = store or InMemoryStore()
    job = store.get_job(job_id)
    publication = store.get_publication(job_id)
    if publication is None:
        return {"job_id": job_id, "status": "UNKNOWN", "reason": "publication missing"}
    raw = adapter.get_status(publication.resolved_provider_post_id())
    updated = reconcile_publication(publication, raw if isinstance(raw, dict) else {})
    store.save_publication(updated)
    if job is not None and job.status != updated.status:
        try:
            job = transition_job(job, updated.status if updated.status in {
                "SCHEDULED", "PUBLISHING", "PUBLISHED", "FAILED", "CANCELLED", "UNKNOWN", "SUBMITTED"
            } else "UNKNOWN")
            store.save_job(job)
        except Exception:
            store.save_job(replace(job, status=updated.status))
    return {
        "job_id": job_id,
        "distribution_job_id": job_id,
        "provider_post_id": updated.resolved_provider_post_id(),
        "platform_object_id": updated.resolved_platform_object_id(),
        "status": updated.status,
        "raw": raw,
    }
