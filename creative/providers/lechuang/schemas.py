"""Xiaole / Lechuang request and result shapes. Unverified video fields are not live."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LechuangAuth:
    base_url: str
    api_key_present: bool
    contract_verified: bool
    reason: str


@dataclass(frozen=True)
class LechuangCapability:
    name: str
    claimed: bool
    verified: bool
    async_mode: bool = True
    reason: str = ""


@dataclass(frozen=True)
class LechuangTaskView:
    provider_task_id: str
    status: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CreateImageRequest:
    prompt: str
    model: str | None = "gpt-image-2"
    image_size: str | None = "2K"
    aspect_ratio: str | None = "9:16"
    n: int = 1
    response_format: str = "b64_json"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CreateImageToImageRequest:
    prompt: str
    source_asset_id: str | None = None
    source_url: str | None = None
    source_path: str | None = None
    strength: float | None = None
    model: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CreateVideoRequest:
    prompt: str
    duration_seconds: float | None = None
    aspect_ratio: str | None = None
    model: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CreateImageToVideoRequest:
    prompt: str
    source_asset_id: str | None = None
    source_url: str | None = None
    source_path: str | None = None
    duration_seconds: float | None = None
    model: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderError:
    code: str
    message: str
    retryable: bool = False
    status_code: int | None = None
    request_id: str | None = None
    raw_response: dict[str, Any] | None = None


@dataclass(frozen=True)
class CreateTaskResponse:
    task_id: str
    status: str
    request_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskStatusResponse:
    task_id: str
    status: str
    progress: float | None = None
    error: ProviderError | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskResultResponse:
    task_id: str
    status: str
    asset_id: str | None = None
    mime_type: str | None = None
    request_id: str | None = None
    credits: float | None = None
    error: ProviderError | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)


REQUEST_TYPES = {
    "generate_image": CreateImageRequest,
    "text_to_image": CreateImageRequest,
    "edit_image": CreateImageToImageRequest,
    "image_to_image": CreateImageToImageRequest,
    "generate_video": CreateVideoRequest,
    "text_to_video": CreateVideoRequest,
    "image_to_video": CreateImageToVideoRequest,
}
