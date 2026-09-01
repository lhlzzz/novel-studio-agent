"""Async generation provider contract. Unsupported stays unsupported."""

from __future__ import annotations

from typing import Any, Protocol

from creative.errors import UnsupportedCapability
from creative.schemas import ProviderTask


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
