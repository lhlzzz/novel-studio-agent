"""Lechuang adapter. Contract methods exist; unsupported or unverified calls fail closed."""

from __future__ import annotations

from typing import Any

from creative.errors import ProviderBlocked, UnsupportedCapability
from creative.providers.base import CapabilityMixin
from creative.providers.lechuang.capabilities import claimed_capabilities, load_models
from creative.providers.lechuang.client import LechuangClient
from creative.schemas import ProviderQuote, ProviderTask

METHOD_TO_CAPABILITY = {
    "generate_text": "text_to_text",
    "generate_image": "text_to_image",
    "edit_image": "image_to_image",
    "generate_video": "text_to_video",
    "extend_video": "video_extend",
    "edit_video": "video_edit",
    "upload_asset": "upload_asset",
}


class LechuangAdapter(CapabilityMixin):
    name = "lechuang"

    def __init__(self, client: LechuangClient | None = None) -> None:
        self.client = client or LechuangClient()
        claimed = {item.name for item in claimed_capabilities()}
        self.supported = frozenset(claimed)
        self.verified_capabilities = frozenset(
            item.name for item in claimed_capabilities() if item.verified
        )

    def live_ready(self) -> tuple[bool, str]:
        return self.client.live_ready()

    def authenticate(self) -> bool:
        return self.live_ready()[0]

    def has_verified(self, capability: str) -> bool:
        return capability in self.verified_capabilities

    def estimate(self, kind: str, payload: dict[str, Any] | None = None) -> float:
        quote = self.quote(kind, payload)
        return float(quote.credits)

    def quote(self, kind: str, payload: dict[str, Any] | None = None) -> ProviderQuote:
        models = load_models()
        credits = 1.0 if "image" in kind else 8.0
        for spec in (models.get("models") or {}).values():
            if kind in (spec.get("capabilities") or []) or METHOD_TO_CAPABILITY.get(kind) in (spec.get("capabilities") or []):
                credits = float(spec.get("cost_credits") or credits)
                break
        return ProviderQuote(credits=credits, mock=False, provider=self.name, parameters={"kind": kind, "source": "claimed"})

    def _blocked_or_unsupported(self, method: str) -> None:
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("lechuang", reason)
        capability = METHOD_TO_CAPABILITY.get(method, method)
        models = load_models()
        verified = bool((models.get("contract") or {}).get("verified"))
        if capability not in self.supported or not verified or capability not in self.verified_capabilities:
            raise UnsupportedCapability(capability, provider="lechuang")

    def create_task(self, kind: str, payload: dict[str, Any]) -> ProviderTask:
        self._blocked_or_unsupported(kind)
        return self.client.create_task(kind, payload)

    def get_task(self, provider_task_id: str) -> ProviderTask:
        self._blocked_or_unsupported("get_task")
        return self.client.get_task(provider_task_id)

    def cancel_task(self, provider_task_id: str) -> ProviderTask:
        self._blocked_or_unsupported("cancel_task")
        return self.client.cancel_task(provider_task_id)

    def get_result(self, provider_task_id: str) -> dict[str, Any]:
        self._blocked_or_unsupported("get_result")
        return self.client.get_result(provider_task_id)

    def generate_text(self, payload: dict[str, Any]) -> ProviderTask:
        return self.create_task("generate_text", payload)

    def generate_image(self, payload: dict[str, Any]) -> ProviderTask:
        return self.create_task("generate_image", payload)

    def edit_image(self, payload: dict[str, Any]) -> ProviderTask:
        return self.create_task("edit_image", payload)

    def generate_video(self, payload: dict[str, Any]) -> ProviderTask:
        return self.create_task("generate_video", payload)

    def extend_video(self, payload: dict[str, Any]) -> ProviderTask:
        return self.create_task("extend_video", payload)

    def edit_video(self, payload: dict[str, Any]) -> ProviderTask:
        return self.create_task("edit_video", payload)

    def upload_asset(self, payload: dict[str, Any]) -> ProviderTask:
        return self.create_task("upload_asset", payload)
