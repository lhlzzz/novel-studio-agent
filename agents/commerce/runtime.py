"""Commerce agent runtime keeps products separate from content."""

from __future__ import annotations

from typing import Any

from commerce.analytics import content_commerce_report
from commerce.models import ContentProductLink, Product


class CommerceAgent:
    name = "commerce-agent"
    owner = "commerce"
    capabilities = ("product", "link", "conversion")
    state_store = "postgres:agent_records"
    tests = ("tests/test_commerce.py",)

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        product = Product(str(task.get("product_id") or "p1"), str(task.get("name") or "Product"))
        link = ContentProductLink(str(task.get("content_package_id") or "pkg"), product.product_id)
        return {
            "agent": self.name,
            "product": product,
            "link": link,
            "report": content_commerce_report(task.get("events") or []),
        }
