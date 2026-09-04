"""Analytics agent runtime owns snapshots, insights, and experiments."""

from __future__ import annotations

from typing import Any

from analytics.insights import build_insight
from analytics.persistence import persist_metric_snapshot, persist_metrics
from analytics.normalizers.metrics import normalize_metrics


class AnalyticsAgent:
    name = "analytics-agent"
    owner = "analytics"
    capabilities = ("snapshot", "insight", "experiment")
    state_store = "postgres:agent_records"
    tests = ("tests/test_analytics_ingestion.py",)

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        raw = dict(task.get("raw") or {})
        if task.get("account_id"):
            raw.setdefault("account_id", task.get("account_id"))
        if task.get("episode_id"):
            raw.setdefault("episode_id", task.get("episode_id"))
        metrics = normalize_metrics(str(task.get("publication_id") or ""), raw, platform=task.get("platform"), post_id=task.get("post_id"))
        persist_metrics(metrics)
        persist_metric_snapshot(metrics)
        insight = build_insight(metrics)
        return {"agent": self.name, "metrics": metrics, "insight": insight}
