"""Provider-agnostic creative generation contract.

Canonical execution lives in `creative/providers/`. This module is the
integration-facing contract, parallel to `integrations/contracts/distribution.py`.
Creative providers generate media. They never publish.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from creative.providers.base import (
    CANONICAL_CAPABILITIES,
    CAPABILITY_ALIASES,
    AsyncGenerationProvider,
    CapabilityMixin,
    CreativeProvider,
)
from creative.schemas import ProviderTask, map_task_status

CREATIVE_TASK_STATES = (
    "SUBMITTED",
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "EXPIRED",
    "UNKNOWN",
)

CREATIVE_TASK_ALIASES = {
    "queued": "QUEUED",
    "running": "RUNNING",
    "processing": "RUNNING",
    "submitted": "SUBMITTED",
    "succeeded": "SUCCEEDED",
    "success": "SUCCEEDED",
    "completed": "SUCCEEDED",
    "failed": "FAILED",
    "cancelled": "CANCELLED",
    "canceled": "CANCELLED",
    "expired": "EXPIRED",
    "timeout": "FAILED",
    "unknown": "UNKNOWN",
    "blocked": "FAILED",
}


def map_creative_status(status: str) -> str:
    raw = str(status or "").strip()
    if raw.upper() in CREATIVE_TASK_STATES:
        return raw.upper()
    aliased = CREATIVE_TASK_ALIASES.get(raw.lower())
    if aliased:
        return aliased
    mapped = map_task_status(raw)
    if mapped == "TIMEOUT":
        return "FAILED"
    if mapped == "BLOCKED":
        return "FAILED"
    if mapped in CREATIVE_TASK_STATES:
        return mapped
    return "UNKNOWN"


@dataclass(frozen=True)
class CreativeGenerationRequest:
    creator_account_id: str
    episode_id: str | None = None
    platform: str = ""
    generation_type: str = "image"
    model: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    aspect_ratio: str = ""
    resolution: str = ""
    duration: str = ""
    references: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    prompt_id: str | None = None
    production_run_id: str | None = None
    idempotency_key: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "model": self.model,
            "image_size": self.resolution,
            "aspect_ratio": self.aspect_ratio,
            "duration": self.duration,
            "account_id": self.creator_account_id,
            "episode_id": self.episode_id,
            "platform": self.platform,
            "prompt_id": self.prompt_id,
            "run_id": self.production_run_id,
            "references": list(self.references),
            "idempotency_key": self.idempotency_key,
            **dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class CreativeArtifact:
    provider_artifact_id: str = ""
    source_url: str = ""
    path: str = ""
    sha256: str = ""
    mime_type: str = ""
    byte_size: int = 0
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    asset_id: str | None = None


@dataclass(frozen=True)
class CreativeTaskStatus:
    provider_task_id: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", map_creative_status(self.status))


@dataclass(frozen=True)
class CreativeGenerationResponse:
    provider: str
    provider_task_id: str
    status: str
    artifact: CreativeArtifact | None = None
    model: str = ""
    cost_status: str = "UNKNOWN"
    cost_snapshot: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", map_creative_status(self.status))


@dataclass(frozen=True)
class CreativeProviderCapabilities:
    name: str
    image: bool = False
    video: bool = False
    image_edit: bool = False
    image_to_video: bool = False
    cancel: bool = False
    webhook: bool = False
    verified: dict[str, bool] = field(default_factory=dict)


class CreativeProviderContract(Protocol):
    name: str

    def generate_image(self, payload: dict[str, Any]) -> ProviderTask: ...
    def generate_video(self, payload: dict[str, Any]) -> ProviderTask: ...
    def get_task(self, provider_task_id: str) -> ProviderTask: ...
    def cancel_task(self, provider_task_id: str) -> ProviderTask: ...
    def download_artifact(self, task: ProviderTask) -> CreativeArtifact: ...
    def verify(self, *, live: bool = False) -> dict[str, Any]: ...
    def capabilities(self) -> dict[str, bool]: ...


__all__ = [
    "CANONICAL_CAPABILITIES",
    "CAPABILITY_ALIASES",
    "CREATIVE_TASK_STATES",
    "AsyncGenerationProvider",
    "CapabilityMixin",
    "CreativeArtifact",
    "CreativeGenerationRequest",
    "CreativeGenerationResponse",
    "CreativeProvider",
    "CreativeProviderCapabilities",
    "CreativeProviderContract",
    "CreativeTaskStatus",
    "ProviderTask",
    "map_creative_status",
]
