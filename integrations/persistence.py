"""In-memory and database stores for jobs, publications, attempts, and uploaded media."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from integrations.contracts.distribution import (
    ContentVariant,
    DistributionAttempt,
    DistributionJob,
    MediaUploadResult,
    Publication,
)


class JobStore(Protocol):
    def save_job(self, job: DistributionJob) -> DistributionJob: ...
    def get_job(self, job_id: str) -> DistributionJob | None: ...
    def get_job_by_idempotency(self, key: str) -> DistributionJob | None: ...
    def save_publication(self, publication: Publication) -> Publication: ...
    def get_publication(self, job_id: str) -> Publication | None: ...
    def list_jobs(self, statuses: tuple[str, ...] | None = None) -> list[DistributionJob]: ...
    def save_media(self, result: MediaUploadResult) -> MediaUploadResult: ...
    def get_media(self, sha256: str) -> MediaUploadResult | None: ...
    def save_attempt(self, attempt: DistributionAttempt) -> DistributionAttempt: ...
    def list_attempts(self, job_id: str) -> list[DistributionAttempt]: ...


@dataclass
class InMemoryStore:
    jobs: dict[str, DistributionJob] = field(default_factory=dict)
    publications: dict[str, Publication] = field(default_factory=dict)
    media: dict[str, MediaUploadResult] = field(default_factory=dict)
    idempotency: dict[str, str] = field(default_factory=dict)
    attempts: dict[str, list[DistributionAttempt]] = field(default_factory=dict)

    def save_job(self, job: DistributionJob) -> DistributionJob:
        self.jobs[job.job_id] = job
        if job.idempotency_key:
            self.idempotency[job.idempotency_key] = job.job_id
        return job

    def get_job(self, job_id: str) -> DistributionJob | None:
        return self.jobs.get(job_id)

    def get_job_by_idempotency(self, key: str) -> DistributionJob | None:
        job_id = self.idempotency.get(key)
        return self.jobs.get(job_id) if job_id else None

    def save_publication(self, publication: Publication) -> Publication:
        self.publications[publication.distribution_job_id] = publication
        return publication

    def get_publication(self, job_id: str) -> Publication | None:
        return self.publications.get(job_id)

    def list_jobs(self, statuses: tuple[str, ...] | None = None) -> list[DistributionJob]:
        jobs = list(self.jobs.values())
        if statuses:
            jobs = [job for job in jobs if job.status in statuses]
        return jobs

    def save_media(self, result: MediaUploadResult) -> MediaUploadResult:
        if result.source_hash:
            self.media[result.source_hash] = result
        return result

    def get_media(self, sha256: str) -> MediaUploadResult | None:
        return self.media.get(sha256)

    def save_attempt(self, attempt: DistributionAttempt) -> DistributionAttempt:
        self.attempts.setdefault(attempt.job_id, []).append(attempt)
        return attempt

    def list_attempts(self, job_id: str) -> list[DistributionAttempt]:
        return list(self.attempts.get(job_id) or [])


class DatabaseStore:
    """Persist distribution records through Meiti PostgreSQL AgentRecord rows."""

    def save_job(self, job: DistributionJob) -> DistributionJob:
        self._write(f"distribution-job:{job.job_id}", "distribution_job", asdict(job))
        if job.idempotency_key:
            self._write(f"distribution-idempotency:{job.idempotency_key}", "distribution_idempotency", {"job_id": job.job_id})
        return job

    def get_job(self, job_id: str) -> DistributionJob | None:
        payload = self._read(f"distribution-job:{job_id}")
        return _job_from_payload(payload) if payload else None

    def get_job_by_idempotency(self, key: str) -> DistributionJob | None:
        payload = self._read(f"distribution-idempotency:{key}")
        if not payload:
            return None
        return self.get_job(str(payload.get("job_id") or ""))

    def save_publication(self, publication: Publication) -> Publication:
        self._write(f"publication:{publication.distribution_job_id}", "publication", asdict(publication))
        return publication

    def get_publication(self, job_id: str) -> Publication | None:
        payload = self._read(f"publication:{job_id}")
        return _publication_from_payload(payload) if payload else None

    def list_jobs(self, statuses: tuple[str, ...] | None = None) -> list[DistributionJob]:
        rows = self._query_type("distribution_job")
        jobs = [_job_from_payload(row) for row in rows if row]
        if statuses:
            jobs = [job for job in jobs if job.status in statuses]
        return jobs

    def save_media(self, result: MediaUploadResult) -> MediaUploadResult:
        self._write(f"media-upload:{result.source_hash}", "media_upload", asdict(result))
        return result

    def get_media(self, sha256: str) -> MediaUploadResult | None:
        payload = self._read(f"media-upload:{sha256}")
        return MediaUploadResult(**payload) if payload else None

    def save_attempt(self, attempt: DistributionAttempt) -> DistributionAttempt:
        self._write(
            f"distribution-attempt:{attempt.job_id}:{attempt.attempt_no}",
            "distribution_attempt",
            asdict(attempt),
        )
        return attempt

    def list_attempts(self, job_id: str) -> list[DistributionAttempt]:
        rows = self._query_type("distribution_attempt")
        attempts = [
            DistributionAttempt(**row)
            for row in rows
            if str(row.get("job_id") or "") == job_id
        ]
        return sorted(attempts, key=lambda item: item.attempt_no)

    @staticmethod
    def _write(record_key: str, record_type: str, payload: dict[str, Any]) -> None:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import AgentRecord

        with SessionLocal() as session:
            row = session.query(AgentRecord).filter_by(record_key=record_key).one_or_none()
            if row is None:
                session.add(AgentRecord(record_key=record_key, record_type=record_type, payload=payload, source="distribution-agent"))
            else:
                row.payload = payload
                row.record_type = record_type
            session.commit()

    @staticmethod
    def _read(record_key: str) -> dict[str, Any] | None:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import AgentRecord

        with SessionLocal() as session:
            row = session.query(AgentRecord).filter_by(record_key=record_key).one_or_none()
            return dict(row.payload) if row is not None else None

    @staticmethod
    def _query_type(record_type: str) -> list[dict[str, Any]]:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import AgentRecord

        with SessionLocal() as session:
            rows = session.query(AgentRecord).filter_by(record_type=record_type).all()
            return [dict(row.payload) for row in rows]


def _job_from_payload(payload: dict[str, Any]) -> DistributionJob:
    variant_payload = dict(payload.get("variant") or {})
    variant = ContentVariant(
        integration_id=str(variant_payload.get("integration_id") or payload.get("integration_id") or ""),
        body=str(variant_payload.get("body") or ""),
        media=tuple(variant_payload.get("media") or ()),
        metadata=dict(variant_payload.get("metadata") or {}),
        title=str(variant_payload.get("title") or ""),
        hashtags=tuple(variant_payload.get("hashtags") or ()),
        cta=str(variant_payload.get("cta") or ""),
        constraints=dict(variant_payload.get("constraints") or {}),
        caption=str(variant_payload.get("caption") or ""),
        hook=str(variant_payload.get("hook") or ""),
        format=str(variant_payload.get("format") or ""),
    )
    return DistributionJob(
        job_id=str(payload.get("job_id") or ""),
        content_package_id=str(payload.get("content_package_id") or ""),
        integration_id=str(payload.get("integration_id") or ""),
        variant=variant,
        action=str(payload.get("action") or "publish"),
        scheduled_at=payload.get("scheduled_at"),
        status=str(payload.get("status") or "DRAFT"),
        idempotency_key=payload.get("idempotency_key"),
        attempt_count=int(payload.get("attempt_count") or 0),
        error_code=payload.get("error_code"),
        error_message=payload.get("error_message"),
        last_attempt_at=payload.get("last_attempt_at"),
        provider_response=payload.get("provider_response"),
        brand_id=payload.get("brand_id"),
        creator_id=payload.get("creator_id"),
        campaign_id=payload.get("campaign_id"),
        request_id=str(payload.get("request_id") or ""),
    )


def _publication_from_payload(payload: dict[str, Any]) -> Publication:
    return Publication(
        distribution_job_id=str(payload.get("distribution_job_id") or ""),
        integration_id=str(payload.get("integration_id") or ""),
        provider=str(payload.get("provider") or ""),
        provider_post_id=str(payload.get("provider_post_id") or payload.get("postiz_post_id") or ""),
        platform_object_id=payload.get("platform_object_id") or payload.get("external_id"),
        status=str(payload.get("status") or "UNKNOWN"),
        published_at=payload.get("published_at"),
        external_url=payload.get("external_url"),
        content_package_id=str(payload.get("content_package_id") or ""),
        request_id=str(payload.get("request_id") or ""),
    )
