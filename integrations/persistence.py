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
from content.models import Campaign, ContentPackage


def _as_datetime(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    from datetime import datetime

    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


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
    def save_content_package(self, package: ContentPackage) -> ContentPackage: ...
    def save_campaign(self, campaign: Campaign) -> Campaign: ...
    def save_integration(self, integration: Any) -> Any: ...


@dataclass
class InMemoryStore:
    jobs: dict[str, DistributionJob] = field(default_factory=dict)
    publications: dict[str, Publication] = field(default_factory=dict)
    media: dict[str, MediaUploadResult] = field(default_factory=dict)
    idempotency: dict[str, str] = field(default_factory=dict)
    attempts: dict[str, list[DistributionAttempt]] = field(default_factory=dict)
    packages: dict[str, ContentPackage] = field(default_factory=dict)
    campaigns: dict[str, Campaign] = field(default_factory=dict)
    integrations: dict[str, Any] = field(default_factory=dict)

    def save_job(self, job: DistributionJob) -> DistributionJob:
        existing = self.get_job_by_idempotency(job.idempotency_key or "")
        if existing is not None and existing.job_id != job.job_id:
            raise ValueError(f"idempotency key already belongs to {existing.job_id}")
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

    def save_content_package(self, package: ContentPackage) -> ContentPackage:
        self.packages[package.package_id] = package
        return package

    def save_campaign(self, campaign: Campaign) -> Campaign:
        self.campaigns[campaign.campaign_id] = campaign
        return campaign

    def save_integration(self, integration: Any) -> Any:
        self.integrations[integration.id] = integration
        return integration


class DatabaseStore:
    """Persist distribution records in their first-class PostgreSQL tables."""

    def save_content_package(self, package: ContentPackage) -> ContentPackage:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import ContentPackageRecord

        with SessionLocal() as session:
            row = session.get(ContentPackageRecord, package.package_id)
            fields = {
                "brand_id": package.brand_id,
                "creator_id": package.creator_id,
                "campaign_id": package.campaign_id,
                "topic": package.topic,
                "content_pillar": package.content_pillar,
                "hook": package.hook,
                "format": package.format,
                "audience": package.audience,
                "title": package.title,
                "caption": package.caption,
                "body": package.body,
                "evidence_ids": list(package.evidence_ids),
                "media_assets": list(package.media_assets),
                "commerce_intent": package.commerce_intent,
                "variants": list(package.variants),
                "metadata_json": package.metadata,
            }
            if row is None:
                row = ContentPackageRecord(package_id=package.package_id, **fields)
                session.add(row)
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
            session.commit()
        return package

    def save_campaign(self, campaign: Campaign) -> Campaign:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import CampaignRecord

        with SessionLocal() as session:
            row = session.get(CampaignRecord, campaign.campaign_id)
            fields = {
                "objective": campaign.objective,
                "audience": campaign.audience,
                "strategy_id": campaign.strategy_id,
                "start_at": campaign.start_at,
                "end_at": campaign.end_at,
                "success_metrics": list(campaign.success_metrics),
                "status": campaign.status,
            }
            if row is None:
                row = CampaignRecord(campaign_id=campaign.campaign_id, **fields)
                session.add(row)
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
            session.commit()
        return campaign

    def save_integration(self, integration: Any) -> Any:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import IntegrationRecord

        with SessionLocal() as session:
            row = session.get(IntegrationRecord, integration.id)
            fields = {
                "provider": integration.provider,
                "platform": getattr(integration, "platform", "") or integration.provider,
                "account_id": integration.account_id,
                "account_name": integration.account_name,
                "region": integration.region,
                "state": integration.state,
                "enabled": int(integration.enabled),
                "capabilities": {
                    key: {
                        "supported": value.supported,
                        "verified": value.verified,
                        "verified_at": value.verified_at,
                        "method": value.method,
                    }
                    for key, value in integration.capabilities.records.items()
                },
                "verified_at": integration.verified_at,
            }
            if row is None:
                row = IntegrationRecord(integration_id=integration.id, **fields)
                session.add(row)
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
            session.commit()
        return integration

    def save_job(self, job: DistributionJob) -> DistributionJob:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import DistributionJobRecord

        if not job.idempotency_key:
            raise ValueError("distribution job requires idempotency_key")
        with SessionLocal() as session:
            row = session.get(DistributionJobRecord, job.job_id)
            fields = {
                "content_package_id": job.content_package_id,
                "integration_id": job.integration_id,
                "action": job.action,
                "status": job.status,
                "idempotency_key": job.idempotency_key,
                "variant": asdict(job.variant),
                "scheduled_at": _as_datetime(job.scheduled_at),
                "last_attempt_at": _as_datetime(job.last_attempt_at),
                "attempt_count": job.attempt_count,
                "error_code": job.error_code,
                "error_message": job.error_message,
                "provider_response": job.provider_response,
                "brand_id": job.brand_id,
                "creator_id": job.creator_id,
                "campaign_id": job.campaign_id,
                "request_id": job.request_id,
            }
            if row is None:
                row = DistributionJobRecord(job_id=job.job_id, **fields)
                session.add(row)
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
            session.commit()
        return job

    def get_job(self, job_id: str) -> DistributionJob | None:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import DistributionJobRecord

        with SessionLocal() as session:
            row = session.get(DistributionJobRecord, job_id)
            if row is None:
                return None
            return _job_from_record(row)

    def get_job_by_idempotency(self, key: str) -> DistributionJob | None:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import DistributionJobRecord

        with SessionLocal() as session:
            row = session.query(DistributionJobRecord).filter_by(idempotency_key=key).one_or_none()
            return _job_from_record(row) if row is not None else None

    def save_publication(self, publication: Publication) -> Publication:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import PublicationRecord

        with SessionLocal() as session:
            row = session.get(PublicationRecord, publication.publication_id)
            fields = {
                "distribution_job_id": publication.distribution_job_id,
                "integration_id": publication.integration_id,
                "provider": publication.provider,
                "provider_post_id": publication.provider_post_id,
                "platform_object_id": publication.platform_object_id,
                "external_url": publication.external_url,
                "status": publication.status,
                "published_at": publication.published_at,
                "content_package_id": publication.content_package_id,
                "request_id": publication.request_id,
            }
            if row is None:
                row = PublicationRecord(publication_id=publication.publication_id, **fields)
                session.add(row)
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
            session.commit()
        return publication

    def get_publication(self, job_id: str) -> Publication | None:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import PublicationRecord

        with SessionLocal() as session:
            row = session.query(PublicationRecord).filter_by(distribution_job_id=job_id).one_or_none()
            return _publication_from_record(row) if row is not None else None

    def list_jobs(self, statuses: tuple[str, ...] | None = None) -> list[DistributionJob]:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import DistributionJobRecord

        with SessionLocal() as session:
            rows = session.query(DistributionJobRecord).all()
            jobs = [_job_from_record(row) for row in rows]
        if statuses:
            jobs = [job for job in jobs if job.status in statuses]
        return jobs

    def save_media(self, result: MediaUploadResult) -> MediaUploadResult:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import MediaUploadRecord

        with SessionLocal() as session:
            row = session.get(MediaUploadRecord, result.source_hash)
            fields = {
                "source_path": result.source_path,
                "mime_type": result.mime_type,
                "size": result.size,
                "provider": result.provider,
                "remote_media_id": result.remote_id,
                "remote_media_path": result.remote_path,
                "status": result.status,
                "uploaded_at": result.uploaded_at,
            }
            if row is None:
                row = MediaUploadRecord(source_hash=result.source_hash, **fields)
                session.add(row)
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
            session.commit()
        return result

    def get_media(self, sha256: str) -> MediaUploadResult | None:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import MediaUploadRecord

        with SessionLocal() as session:
            row = session.get(MediaUploadRecord, sha256)
            if row is None:
                return None
            return MediaUploadResult(
                source_hash=row.source_hash, source_path=row.source_path, mime_type=row.mime_type,
                size=row.size, provider=row.provider, remote_id=row.remote_media_id,
                remote_path=row.remote_media_path, uploaded_at=row.uploaded_at.isoformat(), status=row.status,
            )

    def save_attempt(self, attempt: DistributionAttempt) -> DistributionAttempt:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import DistributionAttemptRecord

        with SessionLocal() as session:
            row = session.get(DistributionAttemptRecord, attempt.attempt_id)
            fields = {
                "distribution_job_id": attempt.distribution_job_id,
                "attempt_no": attempt.attempt_no,
                "provider": "",
                "integration_id": "",
                "started_at": _as_datetime(attempt.started_at),
                "finished_at": _as_datetime(attempt.finished_at),
                "status": attempt.status,
                "error_code": attempt.error_code,
                "error_message": attempt.error_message,
                "provider_request_id": attempt.provider_request_id,
                "response_summary": attempt.response_summary,
                "request_id": attempt.request_id,
                "provider": attempt.provider,
                "integration_id": attempt.integration_id,
            }
            if row is None:
                row = DistributionAttemptRecord(attempt_id=attempt.attempt_id, **fields)
                session.add(row)
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
            session.commit()
        return attempt

    def list_attempts(self, job_id: str) -> list[DistributionAttempt]:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import DistributionAttemptRecord

        with SessionLocal() as session:
            rows = session.query(DistributionAttemptRecord).filter_by(distribution_job_id=job_id).all()
            return sorted((_attempt_from_record(row) for row in rows), key=lambda item: item.attempt_no)

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


def _job_from_record(row: Any) -> DistributionJob:
    return _job_from_payload({
        "job_id": row.job_id,
        "content_package_id": row.content_package_id,
        "integration_id": row.integration_id,
        "variant": row.variant,
        "action": row.action,
        "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
        "last_attempt_at": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
        "status": row.status,
        "idempotency_key": row.idempotency_key,
        "attempt_count": row.attempt_count,
        "error_code": row.error_code,
        "error_message": row.error_message,
        "provider_response": row.provider_response,
        "brand_id": row.brand_id,
        "creator_id": row.creator_id,
        "campaign_id": row.campaign_id,
        "request_id": row.request_id,
    })


def _attempt_from_record(row: Any) -> DistributionAttempt:
    return DistributionAttempt(
        job_id=row.distribution_job_id, distribution_job_id=row.distribution_job_id,
        attempt_id=row.attempt_id, attempt_no=row.attempt_no,
        started_at=row.started_at.isoformat(),
        finished_at=row.finished_at.isoformat() if row.finished_at else None,
        status=row.status, error_code=row.error_code, error_message=row.error_message,
        provider_request_id=row.provider_request_id, response_summary=row.response_summary,
        request_id=row.request_id, provider=row.provider, integration_id=row.integration_id,
    )


def _publication_from_record(row: Any) -> Publication:
    return Publication(
        publication_id=row.publication_id, distribution_job_id=row.distribution_job_id,
        integration_id=row.integration_id, provider=row.provider,
        provider_post_id=row.provider_post_id, platform_object_id=row.platform_object_id,
        status=row.status, published_at=row.published_at.isoformat() if row.published_at else None,
        external_url=row.external_url, content_package_id=row.content_package_id,
        request_id=row.request_id,
    )
