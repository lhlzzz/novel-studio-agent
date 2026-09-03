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
    HandoffOutcome,
    IllegalJobTransition,
    ListingOutcome,
    ProviderError,
    Publication,
    PublicationOutcome,
    make_idempotency_key,
    transition_job,
)
from integrations.persistence import JobStore


class ExternalActionBlocked(RuntimeError):
    """Raised when a distribution job cannot safely leave Meiti."""


class PublicationPersistenceError(ExternalActionBlocked):
    """Raised when a provider succeeded but Meiti could not persist it."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class DistributionService:
    def __init__(self, adapter: DistributionAdapter, store: JobStore) -> None:
        if store is None:
            raise ValueError("DistributionService requires an explicit store")
        self.adapter = adapter
        self.store = store

    def dry_run(self, job: DistributionJob) -> dict[str, Any]:
        account = self._account(job)
        settings = self.adapter.get_settings(account.id)
        errors = list(self.adapter.validate_payload(job))
        if not job.provider or not job.platform:
            errors.append("DistributionJob.provider and platform are required")
        return {
            "status": "BLOCKED" if errors else "READY",
            "account_id": account.id,
            "integration_id": account.id,
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
    ) -> PublicationOutcome | HandoffOutcome | ListingOutcome:
        if not job.provider or not job.platform:
            raise ExternalActionBlocked("DistributionJob.provider and platform are required")
        job = self._ensure_key(job)
        existing = self.store.get_job_by_idempotency(job.idempotency_key or "")
        if existing is not None:
            publication = self.store.get_publication(existing.job_id)
            if publication is not None and existing.status in {"SUBMITTED", "SCHEDULED", "PUBLISHING", "PUBLISHED", "PROCESSING"}:
                return PublicationOutcome(publication=publication, job=existing, request_id=existing.request_id, provider_object_id=publication.provider_post_id)
            handoff = self.store.get_handoff_by_job(existing.job_id)
            if handoff is not None:
                return HandoffOutcome(handoff=handoff, job=existing, request_id=existing.request_id)
            listing = self.store.get_listing_by_job(existing.job_id)
            if listing is not None:
                return ListingOutcome(listing=listing, job=existing, request_id=existing.request_id, provider_object_id=getattr(listing, "provider_item_id", ""))
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
            if job.provider != "xiaohongshu":
                job = self._ensure_media(job)
            job = transition_job(job, "SUBMITTING", last_attempt_at=_utcnow(), attempt_count=attempt_no)
            self.store.save_job(job)
            result = self.adapter.publish(job)
            from social.handoff.models import is_handoff_result
            if is_handoff_result(result) or str(result.get("kind") or "") == "handoff":
                return self._persist_handoff(job, result, attempt_no, started)
            if str(result.get("kind") or result.get("provider_object_type") or "") == "listing":
                return self._persist_listing(job, result, attempt_no, started)
        except IllegalJobTransition as exc:
            job = replace(job, status="FAILED_PERMANENT", error_code="illegal_transition", error_message=str(exc))
            self.store.save_job(job)
            self._record_attempt(job, attempt_no, started, "failed", "illegal_transition", str(exc))
            raise ExternalActionBlocked(str(exc)) from exc
        except ExternalActionBlocked:
            raise
        except Exception as exc:
            retryable = bool(getattr(exc, "retryable", False))
            unknown = bool(getattr(exc, "unknown", False))
            status = "UNKNOWN" if unknown else ("RETRYING" if retryable else "FAILED_PERMANENT")
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
        object_id = str(result.get("provider_object_id") or result.get("post_id") or result.get("id") or "")
        if not object_id:
            job = replace(job, status="FAILED", error_code="missing_provider_object_id", provider_response=result, attempt_count=attempt_no)
            self.store.save_job(job)
            self._record_attempt(job, attempt_no, started, "failed", "missing_provider_object_id", "provider response did not contain an external object id", result)
            raise ExternalActionBlocked("provider response did not contain an external object id")
        account = self._account(job)
        platform_object_id = result.get("external_id") or result.get("externalId") or result.get("platform_object_id")
        remote_status = str(result.get("status") or "SUBMITTED").upper()
        if remote_status in {"PUBLISHED"}:
            status = "SUBMITTED"
            publication_status = "SUBMITTED"
        else:
            status = "SUBMITTED"
            publication_status = remote_status if remote_status in {"SUBMITTED", "PROCESSING", "UNKNOWN"} else "SUBMITTED"
        provider_request_id = result.get("provider_request_id")
        job = transition_job(job, status, provider_response=result)
        self.store.save_job(job)
        publication = Publication(
            distribution_job_id=job.job_id,
            account_id=account.id,
            provider=job.provider,
            provider_post_id=object_id,
            platform_object_id=str(platform_object_id) if platform_object_id is not None else None,
            status=publication_status,
            published_at=result.get("published_at"),
            external_url=result.get("url") or result.get("releaseURL") or result.get("external_url"),
            content_package_id=job.content_package_id,
            request_id=job.request_id,
            platform=job.platform,
            created_at=_utcnow(),
            provider_object_type=str(result.get("provider_object_type") or "publication"),
        )
        try:
            self.store.save_publication(publication)
        except Exception as exc:
            failed = replace(
                job,
                status="UNKNOWN",
                error_code="publication_persistence_failed",
                error_message=str(exc),
                provider_response=result,
            )
            self.store.save_job(failed)
            log_event(
                agent="distribution-agent",
                action="publication_persistence",
                job_id=job.job_id,
                provider=job.provider,
                integration_id=account.id,
                status="INCONSISTENT",
                error_code="publication_persistence_failed",
                request_id=job.request_id,
            )
            raise PublicationPersistenceError(
                "provider action succeeded but Publication persistence failed"
            ) from exc
        self._record_attempt(
            job,
            attempt_no,
            started,
            "success",
            None,
            None,
            {"id": object_id, "status": publication.status},
            provider_request_id=provider_request_id,
            provider_object_id=object_id,
        )
        log_event(
            agent="distribution-agent",
            action=job.action,
            job_id=job.job_id,
            provider=job.provider,
            integration_id=account.id,
            status=publication.status,
            request_id=job.request_id,
        )
        return PublicationOutcome(
            publication=publication,
            job=job,
            request_id=job.request_id,
            provider_request_id=str(provider_request_id) if provider_request_id else None,
            provider_object_id=object_id,
        )

    def _ensure_media(self, job: DistributionJob) -> DistributionJob:
        uploaded = []
        for path in job.variant.media:
            digest = _hash_path(path)
            existing = self.store.get_media(digest, job.provider, job.account_id) if digest else None
            if existing is not None and existing.status in {"UPLOADED", "uploaded"} and (existing.remote_id or getattr(existing, "provider_media_id", "")):
                uploaded.append(existing)
                continue
            result = self.adapter.upload_media(path, account_id=job.account_id, idempotency_key=job.idempotency_key or job.job_id)
            result = replace(result, account_id=job.account_id, provider=job.provider, platform=job.platform or result.platform)
            self.store.save_media(result)
            uploaded.append(result)
        if not job.variant.media:
            return job
        return replace(job, media_uploads=tuple(uploaded))

    def _persist_handoff(self, job, result, attempt_no: int, started: str):
        from social.handoff.models import XHSHandoff
        from social.handoff.export import materialize_handoff_export

        existing = self.store.get_handoff_by_job(job.job_id)
        if existing is not None:
            job = transition_job(job, "SUBMITTED", provider_response=result) if job.status == "SUBMITTING" else job
            self.store.save_job(job)
            self._record_attempt(job, attempt_no, started, "handoff", None, None, {"handoff_id": existing.handoff_id, "status": existing.status})
            return HandoffOutcome(handoff=existing, job=job, request_id=job.request_id)
        handoff_id = str(result.get("handoff_id") or f"xhs-handoff-{job.job_id}")
        package = result.get("package") if isinstance(result.get("package"), dict) else {}
        account = self._account(job)
        job = transition_job(job, "SUBMITTED", provider_response=result)
        self.store.save_job(job)
        handoff = XHSHandoff(
            handoff_id=handoff_id,
            account_id=account.id,
            content_package_id=job.content_package_id,
            status="READY_FOR_XHS",
            export_path="",
            export_status="PENDING",
            content_type=str(package.get("content_type") or result.get("content_type") or ""),
            title=str(package.get("title") or ""),
            content=str(package.get("content") or ""),
            hashtags=tuple(package.get("hashtags") or ()),
            images=tuple(package.get("images") or ()),
            video=package.get("video"),
            cover=package.get("cover"),
            distribution_job_id=job.job_id,
            package=dict(package),
        )
        self.store.save_handoff(handoff)
        try:
            exported = materialize_handoff_export(handoff)
            self.store.save_handoff(exported)
            handoff = exported
        except Exception as exc:
            from dataclasses import replace as _replace
            failed = _replace(handoff, export_status="FAILED")
            self.store.save_handoff(failed)
            raise ExternalActionBlocked(f"XHS handoff export failed: {exc}") from exc
        self._record_attempt(job, attempt_no, started, "handoff", None, None, {"handoff_id": handoff.handoff_id, "status": handoff.status})
        log_event(
            agent="distribution-agent",
            action="handoff",
            job_id=job.job_id,
            provider=job.provider,
            integration_id=account.id,
            status=handoff.status,
            request_id=job.request_id,
        )
        return HandoffOutcome(handoff=handoff, job=job, request_id=job.request_id)

    def _persist_listing(self, job, result, attempt_no: int, started: str):
        from commerce.xianyu import XianyuListing

        existing = self.store.get_listing_by_job(job.job_id)
        if existing is not None:
            job = transition_job(job, "SUBMITTED", provider_response=result) if job.status == "SUBMITTING" else job
            self.store.save_job(job)
            return ListingOutcome(listing=existing, job=job, request_id=job.request_id, provider_object_id=existing.provider_item_id)
        payload = result.get("listing") if isinstance(result.get("listing"), dict) else {}
        object_id = str(result.get("provider_object_id") or result.get("item_id") or result.get("id") or "")
        account = self._account(job)
        job = transition_job(job, "SUBMITTED", provider_response=result)
        self.store.save_job(job)
        listing = XianyuListing(
            listing_id=f"xianyu-listing-{object_id}",
            account_id=account.id,
            title=str(payload.get("title") or job.variant.title or ""),
            description=str(payload.get("description") or job.variant.body or ""),
            price=str(payload.get("price") or ""),
            quantity=int(payload.get("quantity") or 1),
            category_id=str(payload.get("category_id") or ""),
            images=tuple(payload.get("images") or ()),
            condition=str(payload.get("condition") or "new"),
            location=str(payload.get("location") or ""),
            shipping=dict(payload.get("shipping") or {}),
            attributes=dict(payload.get("attributes") or {}),
            commerce_intent="explicit",
            status="SUBMITTED",
            provider_item_id=object_id,
            distribution_job_id=job.job_id,
            content_package_id=job.content_package_id,
            provider_response=dict(result),
        )
        self.store.save_listing(listing)
        self._record_attempt(
            job,
            attempt_no,
            started,
            "listing",
            None,
            None,
            {"listing_id": listing.listing_id, "provider_item_id": object_id},
            provider_request_id=result.get("provider_request_id"),
            provider_object_id=object_id,
        )
        log_event(
            agent="distribution-agent",
            action="listing",
            job_id=job.job_id,
            provider=job.provider,
            integration_id=account.id,
            status=listing.status,
            request_id=job.request_id,
        )
        return ListingOutcome(
            listing=listing,
            job=job,
            request_id=job.request_id,
            provider_request_id=result.get("provider_request_id"),
            provider_object_id=object_id,
        )

    def _account(self, job: DistributionJob):
        return self.adapter.get_account(job.account_id)

    def _record_attempt(
        self,
        job: DistributionJob,
        attempt_no: int,
        started_at: str,
        status: str,
        error_code: str | None,
        error_message: str | None,
        response_summary: dict[str, Any] | None = None,
        *,
        provider_request_id: str | None = None,
        provider_object_id: str | None = None,
    ) -> None:
        self.store.save_attempt(
            DistributionAttempt(
                job_id=job.job_id,
                attempt_no=attempt_no,
                started_at=started_at,
                finished_at=_utcnow(),
                status=status,
                error_code=error_code,
                error_message=error_message,
                provider_request_id=str(provider_request_id) if provider_request_id else None,
                provider_object_id=str(provider_object_id) if provider_object_id else None,
                response_summary=response_summary,
                request_id=job.request_id,
                provider=job.provider,
                integration_id=job.account_id,
            )
        )


def _hash_path(path: str) -> str:
    import hashlib
    from pathlib import Path
    file_path = Path(path)
    if not file_path.exists():
        return hashlib.sha256(path.encode("utf-8")).hexdigest()
    return hashlib.sha256(file_path.read_bytes()).hexdigest()
