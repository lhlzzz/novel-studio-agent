"""Meiti-owned orchestration around a verified distribution adapter."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Any, Callable

from governance.observability import log_event
from integrations.contracts.distribution import (
    DistributionAdapter,
    DistributionAttempt,
    DistributionJob,
    IllegalJobTransition,
    ProviderError,
    Publication,
    make_idempotency_key,
    transition_job,
)
from integrations.persistence import InMemoryStore, JobStore


class ExternalActionBlocked(RuntimeError):
    """Raised when a distribution job cannot safely leave Meiti."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class DistributionService:
    def __init__(self, adapter: DistributionAdapter, store: JobStore | None = None) -> None:
        self.adapter = adapter
        self.store = store or InMemoryStore()

    def dry_run(self, job: DistributionJob) -> dict[str, Any]:
        integration = self.adapter.get_integration(job.integration_id)  # type: ignore[attr-defined]
        settings = self.adapter.get_settings(job.integration_id)  # type: ignore[attr-defined]
        errors = self.adapter.validate_payload(job)  # type: ignore[attr-defined]
        return {
            "status": "BLOCKED" if errors else "READY",
            "integration_id": integration.id,
            "settings": settings,
            "errors": errors,
            "job": asdict(job),
        }

    def _ensure_key(self, job: DistributionJob) -> DistributionJob:
        if job.idempotency_key:
            return job
        return replace(
            job,
            idempotency_key=make_idempotency_key(
                job.content_package_id,
                job.integration_id,
                job.action,
                job.scheduled_at,
            ),
        )

    def execute(
        self,
        job: DistributionJob,
        *,
        gate_check: Callable[[DistributionJob], bool],
    ) -> Publication:
        job = self._ensure_key(job)
        existing = self.store.get_job_by_idempotency(job.idempotency_key or "")
        if existing is not None:
            publication = self.store.get_publication(existing.job_id)
            if publication is not None and existing.status in {"SUBMITTED", "SCHEDULED", "PUBLISHING", "PUBLISHED"}:
                return publication
            job = existing
        started = _utcnow()
        attempt_no = job.attempt_count + 1
        try:
            if job.status == "DRAFT":
                job = transition_job(job, "VALIDATING")
            dry_run = self.dry_run(job)
            if dry_run["status"] != "READY":
                job = transition_job(job, "BLOCKED", error_code="payload_invalid", error_message=str(dry_run["errors"]))
                self.store.save_job(job)
                self._record_attempt(job, attempt_no, started, "blocked", "payload_invalid", str(dry_run["errors"]))
                raise ExternalActionBlocked("distribution payload or capability is invalid")
            if job.status == "VALIDATING":
                job = transition_job(job, "READY")
            if not gate_check(job):
                job = transition_job(job, "BLOCKED", error_code="gate_blocked", error_message="publish gate is not approved")
                self.store.save_job(job)
                self._record_attempt(job, attempt_no, started, "blocked", "gate_blocked", "publish gate is not approved")
                raise ExternalActionBlocked("publish gate is not approved")
            ensure_media = getattr(self.adapter, "ensure_media", None)
            if callable(ensure_media):
                job, _uploaded = ensure_media(job)
            elif job.variant.media:
                upload = getattr(self.adapter, "upload_media", None)
                if not callable(upload):
                    raise ExternalActionBlocked("media must be uploaded before publish")
            job = transition_job(job, "SUBMITTING", last_attempt_at=_utcnow(), attempt_count=attempt_no)
            self.store.save_job(job)
            result = self.adapter.schedule(job) if job.action == "schedule" else self.adapter.publish(job)
        except IllegalJobTransition as exc:
            job = replace(job, status="FAILED_PERMANENT", error_code="illegal_transition", error_message=str(exc))
            self.store.save_job(job)
            self._record_attempt(job, attempt_no, started, "failed", "illegal_transition", str(exc))
            raise ExternalActionBlocked(str(exc)) from exc
        except ExternalActionBlocked:
            raise
        except Exception as exc:
            retryable = bool(getattr(exc, "retryable", False))
            status = "RETRYING" if retryable else "FAILED_PERMANENT"
            if status == "RETRYING" and attempt_no >= 3:
                status = "FAILED_PERMANENT"
            job = replace(
                job,
                status=status,
                error_code=exc.__class__.__name__,
                error_message=str(exc),
                last_attempt_at=_utcnow(),
                attempt_count=attempt_no,
            )
            self.store.save_job(job)
            self._record_attempt(job, attempt_no, started, "retry" if status == "RETRYING" else "failed", exc.__class__.__name__, str(exc))
            if not isinstance(exc, ProviderError):
                wrapped = ProviderError(str(exc))
                wrapped.retryable = retryable
                raise wrapped from exc
            raise
        post_id = str(result.get("id") or result.get("postId") or result.get("post_id") or "")
        if not post_id:
            job = replace(job, status="FAILED", error_code="missing_provider_post_id", provider_response=result, attempt_count=attempt_no)
            self.store.save_job(job)
            self._record_attempt(job, attempt_no, started, "failed", "missing_provider_post_id", "provider response did not contain an external post id", result)
            raise ExternalActionBlocked("provider response did not contain an external post id")
        integration = self.adapter.get_integration(job.integration_id)  # type: ignore[attr-defined]
        platform_object_id = result.get("external_id") or result.get("externalId")
        status = "SCHEDULED" if job.action == "schedule" else "SUBMITTED"
        job = transition_job(job, status, provider_response=result)
        self.store.save_job(job)
        publication = Publication(
            distribution_job_id=job.job_id,
            integration_id=integration.id,
            provider=integration.provider,
            provider_post_id=post_id,
            platform_object_id=str(platform_object_id) if platform_object_id is not None else None,
            status=str(result.get("status") or status),
            published_at=result.get("published_at") or (None if job.action == "schedule" else _utcnow()),
            external_url=result.get("url") or result.get("releaseURL") or result.get("external_url"),
            content_package_id=job.content_package_id,
            request_id=job.request_id,
        )
        self.store.save_publication(publication)
        self._record_attempt(job, attempt_no, started, "success", None, None, {"id": post_id, "status": publication.status})
        log_event(
            agent="distribution-agent",
            action=job.action,
            job_id=job.job_id,
            provider=integration.provider,
            integration_id=integration.id,
            status=publication.status,
            request_id=job.request_id,
        )
        return publication

    def _record_attempt(
        self,
        job: DistributionJob,
        attempt_no: int,
        started_at: str,
        status: str,
        error_code: str | None,
        error_message: str | None,
        response_summary: dict[str, Any] | None = None,
    ) -> None:
        save = getattr(self.store, "save_attempt", None)
        if not callable(save):
            return
        save(
            DistributionAttempt(
                job_id=job.job_id,
                attempt_no=attempt_no,
                started_at=started_at,
                finished_at=_utcnow(),
                status=status,
                error_code=error_code,
                error_message=error_message,
                provider_request_id=(job.provider_response or {}).get("id") if isinstance(job.provider_response, dict) else None,
                response_summary=response_summary,
                request_id=job.request_id,
            )
        )
