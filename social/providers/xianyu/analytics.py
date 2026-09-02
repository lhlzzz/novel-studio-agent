"""Xianyu listing metrics are not ordinary social metrics."""

from __future__ import annotations

from typing import Any


class XianyuAnalyticsClient:
    def __init__(self, client) -> None:
        self.client = client

    def fetch(self, session: str, item_id: str) -> dict[str, Any | None]:
        result = self.client.item_query(session, item_id)
        data = result if isinstance(result, dict) else {}
        inner = data.get("data") if isinstance(data.get("data"), dict) else data
        return {
            "views": None,
            "likes": None,
            "comments": None,
            "shares": None,
            "followers_delta": None,
            "pv": inner.get("pv") if isinstance(inner, dict) else None,
            "click": inner.get("click") if isinstance(inner, dict) else None,
            "inquiry": (inner.get("consult") or inner.get("inquiry")) if isinstance(inner, dict) else None,
            "order": inner.get("order") if isinstance(inner, dict) else None,
        }
