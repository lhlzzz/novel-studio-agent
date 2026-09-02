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
    """Persist the provider-neutral publication without inventing IDs."""
    from integrations.persistence import DatabaseStore

    DatabaseStore().save_publication(publication)


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


def persist_metric_snapshot(metrics: NormalizedMetrics, *, source: str = "native") -> list[dict[str, Any]]:
    observed_at = datetime.now(timezone.utc).isoformat()
    created: list[dict[str, Any]] = []
    durable_publication = False
    try:
        from scripts.db.models import PublicationRecord

        with SessionLocal() as session:
            durable_publication = session.query(PublicationRecord).filter_by(
                distribution_job_id=metrics.publication_id
            ).first() is not None
    except Exception:
        durable_publication = False
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
        key = f"analytics-snapshot:{metrics.publication_id}:{name}:{observed_at}:{source}"
        if not durable_publication:
            continue
        try:
            with SessionLocal() as session:
                from scripts.db.models import MetricSnapshotRecord

                session.add(MetricSnapshotRecord(
                    publication_id=metrics.publication_id,
                    metric_name=name,
                    value=value,
                    observed_at=datetime.fromisoformat(observed_at.replace("Z", "+00:00")).replace(tzinfo=None),
                    source=source,
                ))
                session.commit()
        except Exception as exc:
            # Keep the append-only in-process result useful, but surface DB
            # failure instead of silently claiming durable analytics.
            if "duplicate key" in str(exc).lower() or "unique constraint" in str(exc).lower():
                continue
            raise
    return created
