"""Content-to-product conversion reporting. Missing values stay null, never zero-filled."""

from __future__ import annotations

from typing import Any


def content_commerce_report(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_content: dict[str, dict[str, Any]] = {}
    by_topic: dict[str, dict[str, Any]] = {}
    by_platform: dict[str, dict[str, Any]] = {}
    by_product: dict[str, dict[str, Any]] = {}
    for event in events:
        content_id = str(event.get("content_package_id") or "")
        product_id = str(event.get("product_id") or "")
        platform = str(event.get("platform") or "")
        topic = str(event.get("topic") or "")
        action = str(event.get("action") or "interest")
        conversion = event.get("conversion")
        revenue = event.get("revenue")
        for bucket, key in ((by_content, content_id), (by_product, product_id), (by_platform, platform), (by_topic, topic)):
            if not key:
                continue
            row = bucket.setdefault(key, {"actions": 0, "conversions": None, "revenue": None})
            row["actions"] += 1
            if conversion is not None:
                row["conversions"] = (row["conversions"] or 0) + int(conversion)
            if revenue is not None:
                row["revenue"] = (row["revenue"] or 0) + float(revenue)
            row.setdefault("action", action)
    return {
        "content_interest": by_content,
        "topic_inquiries": by_topic,
        "platform_conversion": by_platform,
        "product_roi": by_product,
    }
