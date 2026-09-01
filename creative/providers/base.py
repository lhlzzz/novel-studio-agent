"""Async generation provider contract. Unsupported stays unsupported."""

from __future__ import annotations

from typing import Any, Protocol

from creative.errors import UnsupportedCapability
from creative.schemas import ProviderTask

CANONICAL_CAPABILITIES = (
    "image_generation",
    "image_to_image",
    "image_to_video",
    "video_generation",
    "vision",
    "video_analysis",
    "audio_generation",
    "audio_analysis",
)

CAPABILITY_ALIASES = {
    "text_to_image": "image_generation",
    "generate_image": "image_generation",
    "edit_image": "image_to_image",
    "text_to_video": "video_generation",
    "generate_video": "video_generation",
}


class AsyncGenerationProvider(Protocol):
    name: str

    def create_task(self, kind: str, payload: dict[str, Any]) -> ProviderTask: ...
    def get_task(self, provider_task_id: str) -> ProviderTask: ...
    def cancel_task(self, provider_task_id: str) -> ProviderTask: ...
    def get_result(self, provider_task_id: str) -> dict[str, Any]: ...


class CapabilityMixin:
    name = "provider"
    supported: frozenset[str] = frozenset()

    def require(self, capability: str) -> None:
        if capability not in self.supported:
            raise UnsupportedCapability(capability, provider=self.name)

    def capabilities(self) -> dict[str, bool]:
        verified = set(getattr(self, "verified_capabilities", ()) or ())
        matrix = {name: False for name in CANONICAL_CAPABILITIES}
        for item in verified:
            matrix[item] = True
            canonical = CAPABILITY_ALIASES.get(item)
            if canonical:
                matrix[canonical] = True
        return matrix

    def create(self, kind: str, payload: dict[str, Any], *, idempotency_key: str | None = None):
        if idempotency_key:
            payload = {**payload, "idempotency_key": idempotency_key}
        return self.create_task(kind, payload)

    def poll(self, provider_task_id: str):
        return self.get_task(provider_task_id)

    def cancel(self, provider_task_id: str):
        return self.cancel_task(provider_task_id)

    def result(self, provider_task_id: str):
        return self.get_result(provider_task_id)

    def health(self) -> dict[str, Any]:
        ready = getattr(self, "live_ready", None)
        if callable(ready):
            ok, reason = ready()
            return {"ok": bool(ok), "reason": reason}
        return {"ok": True, "reason": "ok"}

    def generate_text(self, payload: dict[str, Any]) -> ProviderTask:
        self.require("generate_text")
        return self.create_task("generate_text", payload)

    def generate_image(self, payload: dict[str, Any]) -> ProviderTask:
        self.require("generate_image")
        return self.create_task("generate_image", payload)

    def edit_image(self, payload: dict[str, Any]) -> ProviderTask:
        self.require("edit_image")
        return self.create_task("edit_image", payload)

    def generate_video(self, payload: dict[str, Any]) -> ProviderTask:
        self.require("generate_video")
        return self.create_task("generate_video", payload)

    def extend_video(self, payload: dict[str, Any]) -> ProviderTask:
        self.require("extend_video")
        return self.create_task("extend_video", payload)

    def edit_video(self, payload: dict[str, Any]) -> ProviderTask:
        self.require("edit_video")
        return self.create_task("edit_video", payload)

    def upload_asset(self, payload: dict[str, Any]) -> ProviderTask:
        self.require("upload_asset")
        return self.create_task("upload_asset", payload)


class CreativeProvider(CapabilityMixin):
    """Production provider contract: capabilities/create/poll/cancel/result/health."""
