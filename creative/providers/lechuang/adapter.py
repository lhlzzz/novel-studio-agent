"""Lechuang adapter. Contract methods exist; unsupported or unverified calls fail closed."""

from __future__ import annotations

from typing import Any

from creative.errors import ProviderBlocked, UnsupportedCapability
from creative.providers.base import CapabilityMixin
from creative.providers.lechuang.capabilities import claimed_capabilities, load_models
from creative.providers.lechuang.client import LechuangClient
from creative.schemas import ProviderTask

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

    def live_ready(self) -> tuple[bool, str]:
        return self.client.live_ready()

    def authenticate(self) -> bool:
        return self.live_ready()[0]

    def _blocked_or_unsupported(self, method: str) -> None:
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("lechuang", reason)
        capability = METHOD_TO_CAPABILITY.get(method, method)
        models = load_models()
        verified = bool((models.get("contract") or {}).get("verified"))
        if capability not in self.supported or not verified:
            raise UnsupportedCapability(capability, provider="lechuang")

    def create_task(self, kind: str, payload: dict[str, Any]) -> ProviderTask:
        self._blocked_or_unsupported(kind)
        raise UnsupportedCapability(kind, provider="lechuang")

    def get_task(self, provider_task_id: str) -> ProviderTask:
        self._blocked_or_unsupported("get_task")
        raise UnsupportedCapability("get_task", provider="lechuang")

    def cancel_task(self, provider_task_id: str) -> ProviderTask:
        self._blocked_or_unsupported("cancel_task")
        raise UnsupportedCapability("cancel_task", provider="lechuang")

    def get_result(self, provider_task_id: str) -> dict[str, Any]:
        self._blocked_or_unsupported("get_result")
        raise UnsupportedCapability("get_result", provider="lechuang")

    def generate_text(self, payload: dict[str, Any]) -> ProviderTask:
        self._blocked_or_unsupported("generate_text")
        raise UnsupportedCapability("text_to_text", provider="lechuang")

    def generate_image(self, payload: dict[str, Any]) -> ProviderTask:
        self._blocked_or_unsupported("generate_image")
        raise UnsupportedCapability("text_to_image", provider="lechuang")

    def edit_image(self, payload: dict[str, Any]) -> ProviderTask:
        self._blocked_or_unsupported("edit_image")
        raise UnsupportedCapability("image_to_image", provider="lechuang")

    def generate_video(self, payload: dict[str, Any]) -> ProviderTask:
        self._blocked_or_unsupported("generate_video")
        raise UnsupportedCapability("text_to_video", provider="lechuang")

    def extend_video(self, payload: dict[str, Any]) -> ProviderTask:
        self._blocked_or_unsupported("extend_video")
        raise UnsupportedCapability("video_extend", provider="lechuang")

    def edit_video(self, payload: dict[str, Any]) -> ProviderTask:
        self._blocked_or_unsupported("edit_video")
        raise UnsupportedCapability("video_edit", provider="lechuang")

    def upload_asset(self, payload: dict[str, Any]) -> ProviderTask:
        self._blocked_or_unsupported("upload_asset")
        raise UnsupportedCapability("upload_asset", provider="lechuang")
