"""xAI video generation provider. Creative never publishes. Unverified until real E2E."""

from __future__ import annotations

from typing import Any

from creative.errors import ProviderBlocked, UnsupportedCapability
from creative.providers.base import CapabilityMixin
from creative.providers.xai.client import VIDEO_KINDS, VIDEO_NOT_VERIFIED, XAIVideoClient
from creative.providers.xai.credentials import API_KEY_ENV
from creative.schemas import ProviderQuote, ProviderTask

METHOD_TO_CAPABILITY = {
    "generate_video": "text_to_video",
    "image_to_video": "image_to_video",
    "text_to_video": "text_to_video",
    "video_generation": "video_generation",
}

CLAIMED = frozenset({"text_to_video", "image_to_video", "video_generation", "generate_video"})


class XAIVideoAdapter(CapabilityMixin):
    name = "xai"

    def __init__(self, client: XAIVideoClient | None = None) -> None:
        self.client = client or XAIVideoClient()
        self.supported = CLAIMED
        self.verified_capabilities: frozenset[str] = frozenset()

    def live_ready(self) -> tuple[bool, str]:
        return self.client.live_ready()

    def authenticate(self) -> bool:
        return self.live_ready()[0]

    def has_verified(self, capability: str) -> bool:
        return capability in self.verified_capabilities

    def estimate(self, kind: str, payload: dict[str, Any] | None = None) -> float:
        return float(self.quote(kind, payload).credits)

    def quote(self, kind: str, payload: dict[str, Any] | None = None) -> ProviderQuote:
        return ProviderQuote(
            credits=8.0,
            mock=False,
            provider=self.name,
            parameters={"kind": kind, "model": self.client.model, "source": "xai-video"},
        )

    def create_task(self, kind: str, payload: dict[str, Any]) -> ProviderTask:
        if kind not in VIDEO_KINDS and kind not in CLAIMED:
            raise UnsupportedCapability(kind, provider="xai")
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("xai", reason)
        return self.client.create_task(kind, payload)

    def get_task(self, provider_task_id: str) -> ProviderTask:
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("xai", reason)
        return self.client.get_task(provider_task_id)

    def cancel_task(self, provider_task_id: str) -> ProviderTask:
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("xai", reason)
        return self.client.cancel_task(provider_task_id)

    def get_result(self, provider_task_id: str) -> dict[str, Any]:
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("xai", reason)
        return self.client.get_result(provider_task_id)

    def generate_video(self, payload: dict[str, Any]) -> ProviderTask:
        return self.create_task("generate_video", payload)

    def image_to_video(self, payload: dict[str, Any]) -> ProviderTask:
        return self.create_task("image_to_video", payload)

    def generate_image(self, payload: dict[str, Any]) -> ProviderTask:
        raise UnsupportedCapability("generate_image", provider="xai")

    def capability_status(self, name: str) -> dict[str, Any]:
        ready, reason = self.live_ready()
        if name in {"text_to_video", "image_to_video", "video_generation", "generate_video"}:
            return {
                "status": "NOT_VERIFIED",
                "capability": name,
                "verified": False,
                "reason": VIDEO_NOT_VERIFIED,
                "env": API_KEY_ENV,
                "model": self.client.model,
                "provider": self.name,
                "VIDEO_CONTRACT_VERIFIED": bool(self.client.video_contract_verified),
                "credential_present": bool(self.client.api_key.strip()),
                "live_ready": ready,
                "live_reason": reason,
            }
        return {
            "status": "NOT_VERIFIED",
            "capability": name,
            "verified": False,
            "reason": f"xAI does not own {name}",
            "env": API_KEY_ENV,
            "provider": self.name,
        }
