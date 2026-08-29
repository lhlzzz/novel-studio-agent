"""Persist external publication and normalized analytics through Meiti records."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

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
        payload["provider_post_id"] = publication.resolved_provider_post_id()
        payload["platform_object_id"] = publication.resolved_platform_object_id()
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


SNAPSHOTS: list[dict[str, Any]] = []


def persist_metric_snapshot(metrics: NormalizedMetrics, *, source: str = "postiz") -> list[dict[str, Any]]:
    observed_at = datetime.now(timezone.utc).isoformat()
    created: list[dict[str, Any]] = []
    for name in ("views", "likes", "comments", "shares", "saves", "clicks", "followers_delta"):
        value = metrics.values.get(name)
        snapshot = {
            "timestamp": observed_at,
            "metric": name,
            "value": value,
            "source": source,
            "publication_id": metrics.publication_id,
        }
        SNAPSHOTS.append(snapshot)
        created.append(snapshot)
        key = f"analytics-snapshot:{metrics.publication_id}:{name}:{observed_at}"
        try:
            with SessionLocal() as session:
                session.add(AgentRecord(
                    record_key=key,
                    record_type="metric_snapshot",
                    payload=snapshot,
                    source="analytics-agent",
                ))
                session.commit()
        except Exception:
            continue
    return created
