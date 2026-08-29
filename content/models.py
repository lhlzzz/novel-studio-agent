"""Content owned by Meiti and independent from distribution jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    objective: str
    audience: str = ""
    start_at: str | None = None
    end_at: str | None = None
    strategy_id: str | None = None
    success_metrics: tuple[str, ...] = ()
    status: str = "draft"

    @property
    def id(self) -> str:
        return self.campaign_id


@dataclass(frozen=True)
class ContentPackage:
    package_id: str
    title: str
    body: str
    content_type: str = "post"
    evidence_ids: tuple[str, ...] = ()
    brand_id: str | None = None
    creator_id: str | None = None
    campaign_id: str | None = None
    topic: str = ""
    content_pillar: str = ""
    hook: str = ""
    format: str = "post"
    audience: str = ""
    caption: str = ""
    media_assets: tuple[str, ...] = ()
    commerce_intent: str = "none"
    variants: tuple[str, ...] = ()
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.package_id
