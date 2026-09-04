"""Normalize native social provider analytics without inventing unsupported metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


METRIC_KEYS = (
    "platform", "post_id", "views", "likes", "comments", "shares", "clicks",
    "impressions", "saves", "followers_delta", "published_time", "published_at",
    "account_id", "episode_id", "package_id", "analytics_id", "observed_at",
)


@dataclass(frozen=True)
class NormalizedMetrics:
    publication_id: str
    values: dict[str, Any]


def normalize_metrics(
    publication_id: str,
    raw: dict[str, Any],
    *,
    platform: str | None = None,
    post_id: str | None = None,
) -> NormalizedMetrics:
    values = {key: raw.get(key) for key in METRIC_KEYS}
    values["platform"] = platform or raw.get("platform")
    values["post_id"] = post_id or raw.get("post_id") or publication_id
    values["published_time"] = raw.get("published_time") or raw.get("published_at")
    values["published_at"] = raw.get("published_at") or raw.get("published_time")
    return NormalizedMetrics(publication_id=publication_id, values=values)
