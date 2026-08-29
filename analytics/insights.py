"""Turn normalized metrics into strategy insights instead of raw JSON dumps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from analytics.normalizers.metrics import NormalizedMetrics
from memory.writeback import write_patterns


@dataclass(frozen=True)
class Insight:
    kind: str
    summary: str
    metric: str
    value: Any
    recommendation: str
    confidence: float


def build_insight(metrics: NormalizedMetrics) -> Insight:
    values = metrics.values
    views = values.get("views")
    likes = values.get("likes")
    if views is None and likes is None:
        insight = Insight("insufficient_data", "Provider did not return comparable metrics", "views", None, "keep historical baseline and retry later", 0.2)
    elif isinstance(views, (int, float)) and views >= 0:
        insight = Insight(
            "performance",
            f"Publication {metrics.publication_id} recorded views={views} likes={likes}",
            "views",
            views,
            "keep the hook if CTR/views beat the historical median, otherwise rewrite the first line",
            0.6,
        )
    else:
        insight = Insight("neutral", "Metrics ingested without a dominant signal", "views", views, "collect another snapshot before changing the format", 0.4)
    write_patterns({
        "kind": insight.kind,
        "successful_pattern": insight.summary if insight.kind == "performance" else None,
        "platform_preference": values.get("platform"),
        "content_pattern": insight.recommendation,
        "confidence": insight.confidence,
    })
    return insight


def recommend_next_change(insights: list[Any] | None = None) -> dict[str, str]:
    insights = insights or []
    if not insights:
        return {
            "hook": "test a shorter hook",
            "cta": "reduce CTA pressure",
            "posting_time": "move one hour earlier",
            "structure": "lead with evidence then claim",
            "cover": "try a higher-contrast thumbnail",
        }
    return {
        "hook": "replace the opening line if CTR is below median",
        "cta": "cut the CTA if comments mention sales pressure",
        "posting_time": "reuse the window with higher velocity",
        "structure": "keep the winning content pattern",
        "cover": "swap thumbnail if impressions stall",
    }
