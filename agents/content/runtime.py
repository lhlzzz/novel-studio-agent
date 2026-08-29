"""Content agent runtime produces packages and per-integration variants."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from content.models import Campaign, ContentPackage
from content.variants import build_variant
from memory.retrieval import retrieve


class ContentAgent:
    name = "content-agent"
    owner = "content"
    capabilities = ("package", "variant", "campaign")
    state_store = "postgres:agent_records"
    tests = ("tests/unit/test_commerce.py",)

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        retrieve(task)
        now = datetime.now(timezone.utc).isoformat()
        campaign = None
        if task.get("campaign") or task.get("objective"):
            campaign = Campaign(
                campaign_id=str(task.get("campaign_id") or "campaign-preview"),
                objective=str(task.get("objective") or task.get("campaign") or ""),
                audience=str(task.get("audience") or ""),
                start_at=task.get("start_at"),
                end_at=task.get("end_at"),
                strategy_id=task.get("strategy_id"),
                success_metrics=tuple(task.get("success_metrics") or ()),
                status=str(task.get("campaign_status") or "draft"),
            )
        package = ContentPackage(
            package_id=str(task.get("package_id") or "pkg-preview"),
            title=str(task.get("title") or "Untitled"),
            body=str(task.get("body") or ""),
            content_type=str(task.get("content_type") or task.get("format") or "post"),
            evidence_ids=tuple(task.get("evidence_ids") or ()),
            brand_id=task.get("brand_id"),
            creator_id=task.get("creator_id"),
            campaign_id=(campaign.campaign_id if campaign else task.get("campaign_id")),
            topic=str(task.get("topic") or ""),
            content_pillar=str(task.get("content_pillar") or ""),
            hook=str(task.get("hook") or ""),
            format=str(task.get("format") or task.get("content_type") or "post"),
            audience=str(task.get("audience") or ""),
            caption=str(task.get("caption") or task.get("body") or ""),
            media_assets=tuple(task.get("media_assets") or task.get("media") or ()),
            commerce_intent=str(task.get("commerce_intent") or "none"),
            variants=tuple(task.get("platforms") or ("x",)),
            created_at=now,
            updated_at=now,
            metadata=dict(task.get("metadata") or {}),
        )
        platforms = tuple(task.get("platforms") or package.variants or ("x",))
        variants = [
            build_variant(package, integration_id=str(task.get("integration_id") or platform), platform=platform)
            for platform in platforms
        ]
        return {"agent": self.name, "package": package, "campaign": campaign, "variants": variants}
