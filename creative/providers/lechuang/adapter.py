"""Unified Xiaole / Lechuang creative provider. Image is verified; video is not."""

from __future__ import annotations

from typing import Any

from creative.errors import ProviderBlocked, UnsupportedCapability
from creative.providers.base import CapabilityMixin
from creative.providers.lechuang.capabilities import claimed_capabilities, load_models
from creative.providers.lechuang.client import IMAGE_KINDS, VIDEO_NOT_VERIFIED, LechuangClient
from creative.providers.lechuang.credentials import API_KEY_ENV
from creative.schemas import ProviderQuote, ProviderTask

METHOD_TO_CAPABILITY = {
    "generate_text": "text_to_text",
    "generate_image": "text_to_image",
    "edit_image": "image_to_image",
    "generate_video": "text_to_video",
    "extend_video": "video_extend",
    "edit_video": "video_edit",
    "upload_asset": "upload_asset",
    "image_to_video": "image_to_video",
}

VERIFIED_CAPABILITIES = frozenset({"text_to_image", "image_generation", "generate_image"})
CLAIMED_UNVERIFIED = frozenset({
    "image_to_image",
    "text_to_video",
    "image_to_video",
    "video_generation",
    "video_extend",
    "video_edit",
    "upload_asset",
})


class LechuangAdapter(CapabilityMixin):
    name = "lechuang"

    def __init__(self, client: LechuangClient | None = None) -> None:
        self.client = client or LechuangClient()
        claimed = {item.name for item in claimed_capabilities()}
        self.supported = frozenset(claimed | VERIFIED_CAPABILITIES)
        self.verified_capabilities = frozenset(
            item.name for item in claimed_capabilities() if item.verified
        ) | VERIFIED_CAPABILITIES

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
        credits = 1.0 if "image" in kind or kind in IMAGE_KINDS else 8.0
        for spec in (models.get("models") or {}).values():
            if kind in (spec.get("capabilities") or []) or METHOD_TO_CAPABILITY.get(kind) in (spec.get("capabilities") or []):
                credits = float(spec.get("cost_credits") or credits)
                break
        return ProviderQuote(credits=credits, mock=False, provider=self.name, parameters={"kind": kind, "source": "xiaole-lechuang"})

    def _require_verified(self, method: str) -> None:
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("lechuang", reason)
        capability = METHOD_TO_CAPABILITY.get(method, method)
        if method in IMAGE_KINDS or capability in VERIFIED_CAPABILITIES:
            return
        if capability in CLAIMED_UNVERIFIED or method in CLAIMED_UNVERIFIED:
            raise UnsupportedCapability(capability, provider="lechuang")
        raise UnsupportedCapability(capability, provider="lechuang")

    def create_task(self, kind: str, payload: dict[str, Any]) -> ProviderTask:
        self._require_verified(kind)
        return self.client.create_task(kind, payload)

    def get_task(self, provider_task_id: str) -> ProviderTask:
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("lechuang", reason)
        return self.client.get_task(provider_task_id)

    def cancel_task(self, provider_task_id: str) -> ProviderTask:
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("lechuang", reason)
        return self.client.cancel_task(provider_task_id)

    def get_result(self, provider_task_id: str) -> dict[str, Any]:
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("lechuang", reason)
        return self.client.get_result(provider_task_id)

    def generate_text(self, payload: dict[str, Any]) -> ProviderTask:
        raise UnsupportedCapability("generate_text", provider="lechuang")

    def generate_image(self, payload: dict[str, Any]) -> ProviderTask:
        return self.create_task("generate_image", payload)

    def edit_image(self, payload: dict[str, Any]) -> ProviderTask:
        raise UnsupportedCapability("image_to_image", provider="lechuang")

    def generate_video(self, payload: dict[str, Any]) -> ProviderTask:
        raise UnsupportedCapability("text_to_video", provider="lechuang")

    def extend_video(self, payload: dict[str, Any]) -> ProviderTask:
        raise UnsupportedCapability("video_extend", provider="lechuang")

    def edit_video(self, payload: dict[str, Any]) -> ProviderTask:
        raise UnsupportedCapability("video_edit", provider="lechuang")

    def upload_asset(self, payload: dict[str, Any]) -> ProviderTask:
        raise UnsupportedCapability("upload_asset", provider="lechuang")

    def capability_status(self, name: str) -> dict[str, Any]:
        ready, reason = self.live_ready()
        verified = self.has_verified(name)
        if name in {"text_to_video", "image_to_video", "video_generation", "video_extend", "video_edit"}:
            return {
                "status": "NOT_VERIFIED",
                "capability": name,
                "verified": False,
                "reason": VIDEO_NOT_VERIFIED,
                "env": API_KEY_ENV,
            }
        if name in {"image_to_image", "edit_image"}:
            return {
                "status": "NOT_VERIFIED",
                "capability": name,
                "verified": False,
                "reason": "XiaoleAI image editing is not present in repository evidence",
                "env": API_KEY_ENV,
            }
        if ready and verified:
            return {"status": "PASS", "capability": name, "verified": True, "reason": reason, "env": API_KEY_ENV}
        return {"status": "BLOCKED_EXTERNAL", "capability": name, "verified": verified, "reason": reason, "env": API_KEY_ENV}
