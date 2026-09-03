"""Douyin analytics reads video.data. get_status is not analytics."""

from __future__ import annotations

from typing import Any


class DouyinAnalyticsClient:
    def __init__(self, client) -> None:
        self.client = client

    def fetch(self, access_token: str, open_id: str, item_id: str) -> dict[str, Any | None]:
        result = self.client.video_data(access_token, open_id, [item_id])
        data = result.get("data") if isinstance(result, dict) else {}
        items = data.get("list") if isinstance(data, dict) else None
        stats = (items or [data or result])[0] if isinstance(items, list) and items else (data or result)
        if not isinstance(stats, dict):
            stats = {}
        nested = stats.get("statistics") if isinstance(stats.get("statistics"), dict) else {}
        source = {**nested, **{k: v for k, v in stats.items() if v is not None and k != "statistics"}}
        return {
            "views": _maybe_int(source.get("play_count") if source.get("play_count") is not None else source.get("view_count")),
            "likes": _maybe_int(source.get("digg_count") if source.get("digg_count") is not None else source.get("like_count")),
            "comments": _maybe_int(source.get("comment_count")),
            "shares": _maybe_int(source.get("share_count")),
            "followers_delta": None,
        }


def _maybe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
