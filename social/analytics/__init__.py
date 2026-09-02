"""Native analytics: SocialProvider.analytics() then Meiti snapshots."""

from __future__ import annotations

from typing import Any

from analytics.normalizers.metrics import normalize_metrics
from analytics.persistence import persist_metric_snapshot
from integrations.contracts.distribution import Publication

NULL_KEYS = ("views", "likes", "comments", "shares", "followers_delta")


def collect_analytics(adapter: Any, publication: Publication, *, source: str | None = None) -> dict[str, Any]:
    raw = adapter.analytics(publication) if hasattr(adapter, "analytics") else adapter.get_analytics(publication.provider_post_id)
    payload = {key: (raw or {}).get(key) for key in NULL_KEYS}
    metrics = normalize_metrics(
        publication.publication_id or publication.distribution_job_id,
        payload,
        platform=publication.platform or publication.provider,
        post_id=publication.provider_post_id,
    )
    persist_metric_snapshot(metrics, source=source or f"{publication.provider}:native")
    return payload
