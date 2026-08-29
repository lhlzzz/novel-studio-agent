"""Pull analytics snapshots on a cadence. Unsupported metrics stay null."""

from __future__ import annotations

from typing import Any

from analytics.normalizers.metrics import normalize_metrics
from analytics.persistence import persist_metric_snapshot
from integrations.persistence import InMemoryStore, JobStore

WINDOWS = ("5min", "1h", "6h", "24h", "72h", "7d", "30d")


def run_once(*, adapter: Any, store: JobStore | None = None, window: str = "1h") -> list[dict[str, Any]]:
    if window not in WINDOWS:
        raise ValueError(window)
    store = store or InMemoryStore()
    results = []
    for job in store.list_jobs(("SUBMITTED", "SCHEDULED", "PUBLISHED", "PUBLISHING")):
        publication = store.get_publication(job.job_id)
        if publication is None:
            continue
        raw = adapter.get_analytics(publication.resolved_provider_post_id())
        metrics = normalize_metrics(
            publication.distribution_job_id,
            raw if isinstance(raw, dict) else {},
            platform=publication.provider,
            post_id=publication.resolved_provider_post_id(),
        )
        snapshots = persist_metric_snapshot(metrics, source=f"postiz:{window}")
        results.append({"job_id": job.job_id, "window": window, "snapshots": snapshots})
    return results
