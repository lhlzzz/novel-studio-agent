"""xAI video request and result shapes. Unverified until real E2E evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class XAIAuth:
    base_url: str
    api_key_present: bool
    contract_verified: bool
    reason: str


@dataclass(frozen=True)
class CreateVideoRequest:
    prompt: str
    model: str = "grok-imagine-video-1.5"
    duration_seconds: float | None = 6
    aspect_ratio: str | None = "9:16"
    source_asset_id: str | None = None
    source_url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
