"""Persist external publication and normalized analytics through Meiti records.

Canonical analytics owner is content.models.AnalyticsRecord via ContinuityStore.
AgentRecord and MetricSnapshotRecord are adapter / projection paths only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from analytics.normalizers.metrics import NormalizedMetrics
from integrations.contracts.distribution import Publication
from scripts.db.engine import SessionLocal
from scripts.db.models import AgentRecord

CANONICAL_ANALYTICS_STORE = "content.models.AnalyticsRecord"


def persist_publication(publication: Publication) -> None:
    """Persist the provider-neutral publication without inventing IDs."""
    from integrations.persistence import DatabaseStore

    DatabaseStore().save_publication(publication)


def persist_metrics(metrics: NormalizedMetrics) -> None:
    """Project native metrics. Canonical write is AnalyticsRecord when account-scoped."""
    _persist_canonical_analytics(metrics)
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
            "canonical_store": CANONICAL_ANALYTICS_STORE,
            "projection": True,
        }
        if row is None:
            session.add(AgentRecord(record_key=key, record_type="analytics", payload=payload,
                                    source="analytics-agent"))
        else:
            row.payload = payload
        session.commit()


def _persist_canonical_analytics(metrics: NormalizedMetrics) -> None:
    account_id = metrics.values.get("account_id")
    platform = metrics.values.get("platform")
    if not account_id or not platform:
        return
    try:
        from content.models import AnalyticsRecord
        from content.store import ContinuityStore

        store = ContinuityStore.production()
        store.save_analytics(AnalyticsRecord(
            analytics_id=str(metrics.values.get("analytics_id") or f"pub-{metrics.publication_id}" or uuid4().hex),
            account_id=str(account_id),
            platform=str(platform),
            episode_id=metrics.values.get("episode_id"),
            package_id=metrics.values.get("package_id"),
            publication_id=metrics.publication_id,
            impressions=metrics.values.get("impressions") if metrics.values.get("impressions") is not None else metrics.values.get("views"),
            likes=metrics.values.get("likes"),
            comments=metrics.values.get("comments"),
            shares=metrics.values.get("shares"),
            clicks=metrics.values.get("clicks"),
            followers_delta=metrics.values.get("followers_delta"),
            published_at=metrics.values.get("published_at") or metrics.values.get("published_time"),
            source="native",
        ))
    except Exception:
        return


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
            "durable": bool(durable_publication),
        }
        created.append(snapshot)
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
            if "duplicate key" in str(exc).lower() or "unique constraint" in str(exc).lower():
                continue
            raise
    return created
