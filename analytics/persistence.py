"""Persist external publication and normalized analytics through Meiti records."""

from __future__ import annotations

from dataclasses import asdict

from analytics.normalizers.metrics import NormalizedMetrics
from integrations.contracts.distribution import Publication
from scripts.db.engine import SessionLocal
from scripts.db.models import AgentRecord


def persist_publication(publication: Publication) -> None:
    with SessionLocal() as session:
        row = session.query(AgentRecord).filter_by(
            record_key=f"publication:{publication.distribution_job_id}"
        ).one_or_none()
        payload = asdict(publication)
        payload["external_id"] = publication.external_id
        if row is None:
            session.add(AgentRecord(
                record_key=f"publication:{publication.distribution_job_id}",
                record_type="publication",
                payload=payload,
                source="distribution-agent",
            ))
        else:
            row.payload = payload
        session.commit()


def persist_metrics(metrics: NormalizedMetrics) -> None:
    with SessionLocal() as session:
        key = f"analytics:{metrics.publication_id}"
        row = session.query(AgentRecord).filter_by(record_key=key).one_or_none()
        payload = {
            "publication_id": metrics.publication_id,
            "platform": metrics.values.get("platform"),
            "post_id": metrics.values.get("post_id"),
            "views": metrics.values.get("views"),
            "likes": metrics.values.get("likes"),
            "comments": metrics.values.get("comments"),
            "shares": metrics.values.get("shares"),
            "clicks": metrics.values.get("clicks"),
            "published_time": metrics.values.get("published_time"),
            "metrics": metrics.values,
        }
        if row is None:
            session.add(AgentRecord(record_key=key, record_type="analytics", payload=payload,
                                    source="analytics-agent"))
        else:
            row.payload = payload
        session.commit()
