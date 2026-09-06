"""Xiaole / Lechuang HTTP owner. Official contract from docs.xiaoleai.team."""

from __future__ import annotations

import base64
import binascii
import json
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

from creative.assets import persist_bytes
from creative.errors import AuthError, ProviderBlocked, RateLimited, UnsupportedCapability
from creative.judges.technical import TechnicalQA
from creative.providers.lechuang.credentials import (
    API_KEY_ENV,
    BASE_URL_ENV,
    load_creative_credential,
)
from creative.schemas import ProviderTask, utcnow

IMAGE_ENDPOINT = "/images/generations"
VIDEO_CREATE_ENDPOINT = "/videos"
VIDEO_STATUS_ENDPOINT = "/videos/{video_id}"
VIDEO_CONTENT_ENDPOINT = "/videos/{video_id}/content"
SUPPORTED_MODELS = {
    "gpt-image-2",
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
}
SUPPORTED_SIZES = {"512", "1K", "2K", "4K"}
SUPPORTED_ASPECT_RATIOS = {
    "1:1", "16:9", "9:16", "3:2", "2:3", "4:3", "3:4", "5:4", "4:5", "21:9",
}
SUPPORTED_QUALITY = {"low", "medium", "high"}
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_IMAGE_SIZE = "2K"
DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_QUALITY = "high"
IMAGE_TIMEOUT_SECONDS = 600
VIDEO_CREATE_TIMEOUT_SECONDS = 300
VIDEO_POLL_TIMEOUT_SECONDS = 300
VIDEO_CONTENT_TIMEOUT_SECONDS = 600
VIDEO_MAX_WAIT_SECONDS = 1200
VIDEO_POLL_SECONDS = 3
MAX_POLL_COUNT = 400
MAX_WAIT_SECONDS = VIDEO_MAX_WAIT_SECONDS
BACKOFF_SECONDS = (3, 3, 3, 3, 3)
IMAGE_CONTRACT_VERIFIED = True
VIDEO_CONTRACT_VERIFIED = False
CONTRACT_VERIFIED = IMAGE_CONTRACT_VERIFIED
MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
IMAGE_KINDS = frozenset({"generate_image", "text_to_image", "image_generation"})
VIDEO_KINDS = frozenset({
    "generate_video",
    "text_to_video",
    "video_generation",
    "image_to_video",
})
UNVERIFIED_KINDS = frozenset({
    "edit_image",
    "image_to_image",
    "extend_video",
    "video_extend",
    "edit_video",
    "video_edit",
    "upload_asset",
})
VIDEO_MODELS = {
    "grok-video": {
        "seconds": (6, 10, 12, 16, 20),
        "default_seconds": 6,
        "sizes": ("1280x720", "720x1280", "1024x1024", "1792x1024"),
        "resolutions": ("480p", "720p"),
        "presets": ("fun", "normal", "spicy", "custom"),
        "text_to_video": True,
        "image_to_video": True,
        "max_references": 7,
    },
    "video-ds-2.0": {
        "seconds": (15,),
        "default_seconds": 15,
        "sizes": ("1280x720", "720x1280", "1024x1024", "848x480", "1696x960", "1920x1080"),
        "resolutions": (),
        "presets": (),
        "text_to_video": True,
        "image_to_video": True,
        "max_references": 1,
    },
    "video-ds-2.0-fast": {
        "seconds": (15,),
        "default_seconds": 15,
        "sizes": ("1280x720", "720x1280", "1024x1024", "848x480", "1696x960", "1920x1080"),
        "resolutions": (),
        "presets": (),
        "text_to_video": True,
        "image_to_video": True,
        "max_references": 1,
    },
}
DEFAULT_VIDEO_MODEL = "grok-video"
VIDEO_SIZE_BY_RATIO = {
    "1:1": "1024x1024",
    "16:9": "1280x720",
    "9:16": "720x1280",
}
VIDEO_SUCCEEDED = frozenset({"completed", "succeeded", "success", "done"})
VIDEO_FAILED = frozenset({"failed", "error", "cancelled", "canceled", "expired"})
VIDEO_RUNNING = frozenset({
    "queued", "pending", "submitted", "not_start", "in_progress",
    "processing", "running", "finalizing",
})
VIDEO_NOT_VERIFIED = "Lechuang video API is documented; live verification has not succeeded"


def decode_image(value: Any) -> tuple[bytes, str]:
    raw = str(value or "").strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    raw = "".join(raw.split())
    try:
        image_bytes = base64.b64decode(raw + "=" * ((4 - len(raw) % 4) % 4), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProviderBlocked("lechuang", "b64_json is not valid Base64") from exc
    if not image_bytes:
        raise ProviderBlocked("lechuang", "decoded image is empty")
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return image_bytes, ".png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return image_bytes, ".jpg"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return image_bytes, ".gif"
    if len(image_bytes) >= 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return image_bytes, ".webp"
    raise ProviderBlocked("lechuang", "b64_json is not a supported PNG/JPEG/GIF/WEBP image")


def inspect_image_bytes(image_bytes: bytes) -> tuple[int, int, str]:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n") and len(image_bytes) >= 24:
        width = int.from_bytes(image_bytes[16:20], "big")
        height = int.from_bytes(image_bytes[20:24], "big")
        if width <= 0 or height <= 0:
            raise ProviderBlocked("lechuang", "image width/height invalid")
        return width, height, "image/png"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")) and len(image_bytes) >= 10:
        width = int.from_bytes(image_bytes[6:8], "little")
        height = int.from_bytes(image_bytes[8:10], "little")
        if width <= 0 or height <= 0:
            raise ProviderBlocked("lechuang", "image width/height invalid")
        return width, height, "image/gif"
    if len(image_bytes) >= 30 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return 1, 1, "image/webp"
    from io import BytesIO
    try:
        from PIL import Image
    except ImportError as exc:
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return 1, 1, "image/jpeg"
        raise ProviderBlocked("lechuang", "image inspector unavailable") from exc
    with Image.open(BytesIO(image_bytes)) as image:
        width, height = image.size
        fmt = (image.format or "").lower()
    if width <= 0 or height <= 0:
        raise ProviderBlocked("lechuang", "image width/height invalid")
    mime = {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(fmt, "image/png")
    return width, height, mime


def parse_error_payload(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        for key in ("message", "detail"):
            if payload.get(key):
                return str(payload[key])
    return fallback


def map_remote_video_status(status: str) -> str:
    raw = str(status or "").strip().lower()
    if raw in VIDEO_SUCCEEDED:
        return "succeeded"
    if raw in {"cancelled", "canceled"}:
        return "cancelled"
    if raw == "expired":
        return "expired"
    if raw in VIDEO_FAILED:
        return "failed"
    if raw in {"submitted"}:
        return "submitted"
    if raw in VIDEO_RUNNING:
        return "running" if raw in {"in_progress", "processing", "running", "finalizing"} else "queued"
    return "unknown"


def video_size_for(aspect_ratio: str, explicit: str = "") -> str:
    size = str(explicit or "").strip().lower().replace("×", "x")
    if size:
        return size
    return VIDEO_SIZE_BY_RATIO.get(str(aspect_ratio or "").strip(), "720x1280")


def normalize_video_seconds(model: str, value: Any) -> int:
    spec = VIDEO_MODELS[model]
    allowed = spec["seconds"]
    try:
        seconds = int(float(str(value or "").strip() or spec["default_seconds"]))
    except (TypeError, ValueError):
        seconds = int(spec["default_seconds"])
    if seconds in allowed:
        return seconds
    lower = [item for item in allowed if item <= seconds]
    return int(lower[-1] if lower else allowed[0])


def encode_multipart(fields: dict[str, str], files: list[tuple[str, str, bytes, str]]) -> tuple[bytes, str]:
    boundary = f"----MeitiLechuang{uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        )
    for field_name, filename, content, mime in files:
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8")
        chunks.append(header + content + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def inspect_video_bytes(video_bytes: bytes) -> tuple[int, int, float, str]:
    if len(video_bytes) < 8:
        raise ProviderBlocked("lechuang", "video result is empty")
    if video_bytes[4:8] != b"ftyp" and not video_bytes.startswith(b"\x00\x00\x00"):
        if b"ftyp" not in video_bytes[:32]:
            raise ProviderBlocked("lechuang", "video result is not MP4")
    return 0, 0, 0.0, "video/mp4"

class LechuangClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        *,
        asset_root=None,
    ) -> None:
        self.credential = load_creative_credential(api_key=api_key, base_url=base_url)
        self.base_url = self.credential.endpoint
        self.api_key = self.credential.api_key
        self.contract_verified = IMAGE_CONTRACT_VERIFIED
        self.video_contract_verified = VIDEO_CONTRACT_VERIFIED
        self.contract_reason = "XiaoleAI official image API POST /images/generations, response_format=b64_json"
        self.video_reason = VIDEO_NOT_VERIFIED
        self.max_poll_count = MAX_POLL_COUNT
        self.max_wait_seconds = MAX_WAIT_SECONDS
        self.backoff_seconds = BACKOFF_SECONDS
        self.asset_root = asset_root
        self._tasks: dict[str, ProviderTask] = {}
        self._idempotency: dict[str, str] = {}
        self._sleep = time.sleep

    def auth(self):
        from creative.providers.lechuang.schemas import LechuangAuth

        ready, reason = self.live_ready()
        return LechuangAuth(
            base_url=self.base_url,
            api_key_present=bool(self.api_key.strip()),
            contract_verified=self.contract_verified,
            reason="" if ready else reason,
        )

    def live_ready(self) -> tuple[bool, str]:
        if not self.api_key.strip():
            return False, f"{API_KEY_ENV} missing"
        if not self.base_url:
            return False, f"{BASE_URL_ENV} missing"
        if not self.contract_verified:
            return False, self.contract_reason
        return True, "ok"

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        self._require_ready()
        if not path:
            raise ProviderBlocked("lechuang", "Xiaole image endpoint missing")
        return self._http(method, path, **kwargs)

    def map_http_error(self, status_code: int, body: str = "", headers: dict[str, str] | None = None) -> None:
        if int(status_code) in {401, 403}:
            raise AuthError("Xiaole/Lechuang authentication failed", provider="lechuang")
        if int(status_code) == 429:
            self.handle_rate_limit(status_code, headers)
        if int(status_code) >= 500:
            raise ProviderBlocked("lechuang", f"provider failure HTTP {status_code}", details={"retryable": True, "body": body[:300]})
        raise ProviderBlocked("lechuang", f"invalid response HTTP {status_code}", details={"body": body[:300]})

    def _require_ready(self) -> None:
        ready, reason = self.live_ready()
        if ready:
            return
        if API_KEY_ENV in reason:
            raise AuthError(reason, provider="lechuang")
        raise ProviderBlocked("lechuang", reason)

    def _headers(self, *, content_type: str | None = "application/json", accept: str = "application/json") -> dict[str, str]:
        headers = {
            "Accept": accept,
            "Authorization": f"Bearer {self.api_key}",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _http(self, method: str, path: str, **kwargs: Any) -> Any:
        timeout = float(kwargs.pop("timeout", 30))
        binary = bool(kwargs.pop("binary", False))
        url = path if str(path).startswith("http") else f"{self.base_url}{path}"
        payload = kwargs.get("json")
        data = kwargs.get("data")
        content_type = kwargs.get("content_type")
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            content_type = content_type or "application/json"
        accept = "application/octet-stream" if binary else "application/json"
        request = Request(
            url,
            data=data,
            headers=self._headers(content_type=content_type, accept=accept),
            method=method.upper(),
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                if binary:
                    if not raw:
                        raise ProviderBlocked("lechuang", "missing result")
                    return raw
                decoded = raw.decode("utf-8")
                if not decoded:
                    raise ProviderBlocked("lechuang", "missing result")
                try:
                    body = json.loads(decoded)
                except json.JSONDecodeError as exc:
                    raise ProviderBlocked("lechuang", "invalid response") from exc
                if isinstance(body, dict) and body.get("error"):
                    raise ProviderBlocked("lechuang", parse_error_payload(body, "provider error"))
                return body
        except HTTPError as exc:
            body = exc.read().decode("utf-8", "replace") if hasattr(exc, "read") else str(exc)
            headers = {key: value for key, value in (exc.headers.items() if exc.headers else [])}
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = {}
            message = parse_error_payload(parsed, body[:300] or f"HTTP {exc.code}")
            if int(exc.code) in {401, 403, 429} or int(exc.code) >= 500:
                self.map_http_error(exc.code, message, headers)
            raise ProviderBlocked("lechuang", f"invalid response HTTP {exc.code}: {message}")
        except TimeoutError as exc:
            raise ProviderBlocked("lechuang", "HTTP timeout", details={"retryable": True}) from exc
        except URLError as exc:
            raise ProviderBlocked("lechuang", f"provider failure: {exc.reason}", details={"retryable": True}) from exc

    def create_task(self, kind: str, payload: dict[str, Any]) -> ProviderTask:
        if kind in UNVERIFIED_KINDS:
            raise UnsupportedCapability(kind, provider="lechuang")
        if kind in IMAGE_KINDS:
            return self.generate_image(payload)
        if kind in VIDEO_KINDS:
            return self.generate_video(payload)
        raise UnsupportedCapability(kind, provider="lechuang")

    def get_task(self, provider_task_id: str) -> ProviderTask:
        task = self._tasks.get(provider_task_id)
        if task is None:
            raise ProviderBlocked("lechuang", "provider task not found")
        if task.kind in VIDEO_KINDS and task.status not in {"succeeded", "failed", "cancelled", "expired"}:
            return self.poll_video(provider_task_id, wait=False)
        return task

    def cancel_task(self, provider_task_id: str) -> ProviderTask:
        task = self._tasks.get(provider_task_id)
        if task is None:
            raise ProviderBlocked("lechuang", "provider task not found")
        cancelled = ProviderTask(
            provider=task.provider,
            provider_task_id=task.provider_task_id,
            status="cancelled",
            kind=task.kind,
            result=task.result,
            poll_count=task.poll_count,
        )
        self._tasks[provider_task_id] = cancelled
        return cancelled

    def get_result(self, provider_task_id: str) -> dict[str, Any]:
        task = self.get_task(provider_task_id)
        if task.status != "succeeded":
            return {"status": task.status, "error": task.error}
        return task.result

    def generate_image(self, payload: dict[str, Any]) -> ProviderTask:
        self._require_ready()
        key = str((payload or {}).get("idempotency_key") or "")
        if key and key in self._idempotency:
            return self.get_task(self._idempotency[key])
        prompt = str((payload or {}).get("prompt") or "").strip()
        if not prompt:
            raise ProviderBlocked("lechuang", "prompt is required")
        model = str((payload or {}).get("model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
        if model not in SUPPORTED_MODELS:
            raise ProviderBlocked("lechuang", f"unsupported image model: {model}")
        image_size = str((payload or {}).get("image_size") or DEFAULT_IMAGE_SIZE).strip() or DEFAULT_IMAGE_SIZE
        if image_size not in SUPPORTED_SIZES:
            raise ProviderBlocked("lechuang", f"unsupported image_size: {image_size}")
        aspect_ratio = str((payload or {}).get("aspect_ratio") or DEFAULT_ASPECT_RATIO).strip() or DEFAULT_ASPECT_RATIO
        if aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
            raise ProviderBlocked("lechuang", f"unsupported aspect_ratio: {aspect_ratio}")
        quality = str((payload or {}).get("quality") or DEFAULT_QUALITY).strip() or DEFAULT_QUALITY
        if quality not in SUPPORTED_QUALITY:
            raise ProviderBlocked("lechuang", f"unsupported quality: {quality}")
        n = int((payload or {}).get("n") or 1)
        if n < 1 or n > 4:
            raise ProviderBlocked("lechuang", "n must be between 1 and 4")
        if model != "gpt-image-2" and n != 1:
            raise ProviderBlocked("lechuang", "non gpt-image-2 models only support n=1")
        request_payload = {
            "model": model,
            "prompt": prompt,
            "response_format": "b64_json",
            "image_size": image_size,
            "aspect_ratio": aspect_ratio,
            "quality": quality,
            "n": n,
        }
        body = self._http("POST", IMAGE_ENDPOINT, json=request_payload, timeout=IMAGE_TIMEOUT_SECONDS)
        if not isinstance(body, dict):
            raise ProviderBlocked("lechuang", "invalid response schema")
        items = body.get("data")
        if not isinstance(items, list) or not items:
            raise ProviderBlocked("lechuang", "image HTTP success but data is empty")
        first = items[0]
        if not isinstance(first, dict) or not first.get("b64_json"):
            raise ProviderBlocked("lechuang", "data[0] missing b64_json")
        image_bytes, suffix = decode_image(first["b64_json"])
        width, height, mime = inspect_image_bytes(image_bytes)
        if first.get("mime_type"):
            mime = str(first.get("mime_type"))
        if mime != MIME_BY_SUFFIX.get(suffix, mime):
            mime = MIME_BY_SUFFIX.get(suffix, mime)
        request_id = str(body.get("request_id") or body.get("id") or "")
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        cost_status = "KNOWN" if usage.get("image_credits_charged") is not None else "UNKNOWN"
        asset = persist_bytes(
            image_bytes,
            asset_type="image",
            suffix=suffix,
            root=self.asset_root,
            mime_type=mime,
            width=width,
            height=height,
            workflow_id=(payload or {}).get("workflow_id"),
            workflow_version=(payload or {}).get("workflow_version"),
            creative_run_id=(payload or {}).get("run_id"),
            prompt_id=(payload or {}).get("prompt_id"),
            character_id=(payload or {}).get("character_id"),
            account_id=(payload or {}).get("account_id"),
            series_id=(payload or {}).get("series_id"),
            episode_id=(payload or {}).get("episode_id"),
            content_package_id=(payload or {}).get("content_package_id"),
            creative_context_id=(payload or {}).get("creative_context_id"),
            world_id=(payload or {}).get("world_id"),
            provider="xiaole-lechuang",
            provider_task_id=request_id,
            model=str(body.get("model") or model),
            generation_mode="PROVIDER_API",
            tool="lechuang",
            metadata={
                "provider": "xiaole",
                "service": "lechuang",
                "provider_task_id": request_id,
                "model": str(body.get("model") or model),
                "image_size": image_size,
                "aspect_ratio": aspect_ratio,
                "quality": quality,
                "source": "xiaole-lechuang",
                "source_url": "",
                "created_at": utcnow(),
                "account_id": (payload or {}).get("account_id"),
                "series_id": (payload or {}).get("series_id"),
                "episode_id": (payload or {}).get("episode_id"),
                "creative_context_id": (payload or {}).get("creative_context_id"),
                "usage": usage,
            },
        )
        qa = TechnicalQA().inspect_image(asset)
        if qa.get("decision") != "pass":
            raise ProviderBlocked("lechuang", "technical qa failed", details={"qa": qa})
        task_id = request_id or asset.sha256
        result = {
            "asset": asset,
            "asset_id": asset.asset_id,
            "path": asset.path,
            "sha256": asset.sha256,
            "mime_type": mime,
            "byte_size": asset.size,
            "width": width,
            "height": height,
            "provider_artifact_id": request_id,
            "source_url": "",
            "request_id": request_id,
            "qa": qa,
            "model": str(body.get("model") or model),
            "cost_status": cost_status,
            "cost_snapshot": {"status": cost_status, "usage": usage, "resolution": image_size, "aspect_ratio": aspect_ratio, "quality": quality},
        }
        if key:
            result["idempotency_key"] = key
        task = ProviderTask(
            provider="lechuang",
            provider_task_id=task_id,
            status="succeeded",
            kind="generate_image",
            result=result,
        )
        self._tasks[task_id] = task
        if key:
            self._idempotency[key] = task_id
        return task

    def generate_video(self, payload: dict[str, Any], *, wait: bool = False) -> ProviderTask:
        self._require_ready()
        key = str((payload or {}).get("idempotency_key") or "")
        if key and key in self._idempotency:
            return self.get_task(self._idempotency[key])
        prompt = str((payload or {}).get("prompt") or "").strip()
        if not prompt:
            raise ProviderBlocked("lechuang", "prompt is required")
        model = str((payload or {}).get("model") or DEFAULT_VIDEO_MODEL).strip() or DEFAULT_VIDEO_MODEL
        if model not in VIDEO_MODELS:
            raise ProviderBlocked("lechuang", f"unsupported video model: {model}")
        spec = VIDEO_MODELS[model]
        kind = str((payload or {}).get("kind") or (payload or {}).get("generation_type") or "").strip().lower()
        references = self._reference_files(payload or {})
        if kind in {"image_to_video"} and not references:
            raise ProviderBlocked("lechuang", "image_to_video requires input_reference[]")
        if references and not spec["image_to_video"]:
            raise ProviderBlocked("lechuang", f"{model} does not support image_to_video")
        if not references and not spec["text_to_video"]:
            raise ProviderBlocked("lechuang", f"{model} requires input_reference[]")
        if len(references) > int(spec["max_references"]):
            raise ProviderBlocked("lechuang", f"{model} supports at most {spec['max_references']} reference image(s)")
        seconds = normalize_video_seconds(model, (payload or {}).get("seconds") or (payload or {}).get("duration"))
        aspect_ratio = str((payload or {}).get("aspect_ratio") or DEFAULT_ASPECT_RATIO).strip() or DEFAULT_ASPECT_RATIO
        size = video_size_for(aspect_ratio, str((payload or {}).get("size") or ""))
        if size not in spec["sizes"]:
            size = spec["sizes"][0]
        fields = {
            "model": model,
            "prompt": prompt,
            "seconds": str(seconds),
            "size": size,
        }
        resolution = str((payload or {}).get("resolution_name") or (payload or {}).get("resolution") or "").strip()
        if spec["resolutions"]:
            fields["resolution_name"] = resolution if resolution in spec["resolutions"] else "720p"
        elif resolution:
            raise ProviderBlocked("lechuang", f"{model} does not accept resolution_name")
        preset = str((payload or {}).get("preset") or "").strip()
        if spec["presets"]:
            fields["preset"] = preset if preset in spec["presets"] else "normal"
        elif preset:
            raise ProviderBlocked("lechuang", f"{model} does not accept preset")
        body_bytes, content_type = encode_multipart(fields, references)
        remote = self._http(
            "POST",
            VIDEO_CREATE_ENDPOINT,
            data=body_bytes,
            content_type=content_type,
            timeout=VIDEO_CREATE_TIMEOUT_SECONDS,
        )
        if not isinstance(remote, dict):
            raise ProviderBlocked("lechuang", "invalid video create schema")
        video_id = str(remote.get("id") or remote.get("task_id") or "").strip()
        if not video_id:
            raise ProviderBlocked("lechuang", "video task created but id/task_id missing")
        mapped = map_remote_video_status(str(remote.get("status") or "queued"))
        result = {
            "model": model,
            "seconds": seconds,
            "size": size,
            "aspect_ratio": aspect_ratio,
            "resolution_name": fields.get("resolution_name"),
            "preset": fields.get("preset"),
            "source_url": f"{self.base_url}{VIDEO_CONTENT_ENDPOINT.format(video_id=quote(video_id, safe=''))}",
            "retrieve_url": f"{self.base_url}{VIDEO_STATUS_ENDPOINT.format(video_id=quote(video_id, safe=''))}",
            "raw": remote,
            "cost_status": "UNKNOWN",
            "cost_snapshot": {"status": "UNKNOWN", "model": model, "seconds": seconds, "size": size},
            "account_id": (payload or {}).get("account_id"),
            "episode_id": (payload or {}).get("episode_id"),
            "prompt_id": (payload or {}).get("prompt_id"),
            "run_id": (payload or {}).get("run_id"),
            "source_asset_id": (payload or {}).get("source_asset_id"),
            "kind": "image_to_video" if references else "generate_video",
        }
        if key:
            result["idempotency_key"] = key
        task = ProviderTask(
            provider="lechuang",
            provider_task_id=video_id,
            status=mapped,
            kind=result["kind"],
            result=result,
        )
        self._tasks[video_id] = task
        if key:
            self._idempotency[key] = video_id
        if wait or mapped == "succeeded":
            return self.poll_video(video_id, wait=True)
        return task

    def poll_video(self, provider_task_id: str, *, wait: bool = False) -> ProviderTask:
        self._require_ready()
        video_id = str(provider_task_id or "").strip()
        if not video_id:
            raise ProviderBlocked("lechuang", "provider task not found")
        deadline = time.time() + (VIDEO_MAX_WAIT_SECONDS if wait else 0)
        poll_count = 0
        last: ProviderTask | None = None
        while True:
            remote = self._http(
                "GET",
                VIDEO_STATUS_ENDPOINT.format(video_id=quote(video_id, safe="")),
                timeout=VIDEO_POLL_TIMEOUT_SECONDS,
            )
            if not isinstance(remote, dict):
                raise ProviderBlocked("lechuang", "invalid video status schema")
            mapped = map_remote_video_status(str(remote.get("status") or ""))
            existing = self._tasks.get(video_id)
            result = dict(existing.result if existing else {})
            result["raw"] = remote
            result["source_url"] = f"{self.base_url}{VIDEO_CONTENT_ENDPOINT.format(video_id=quote(video_id, safe=''))}"
            error = None
            if mapped in {"failed", "cancelled", "expired"}:
                err = remote.get("error")
                if isinstance(err, dict):
                    error = str(err.get("message") or err)
                else:
                    error = str(err or remote.get("message") or f"video {mapped}")
            last = ProviderTask(
                provider="lechuang",
                provider_task_id=video_id,
                status=mapped,
                kind=(existing.kind if existing else "generate_video"),
                result=result,
                error=error,
                poll_count=poll_count,
            )
            self._tasks[video_id] = last
            if mapped == "succeeded":
                return self._materialize_video(last)
            if mapped in {"failed", "cancelled", "expired"}:
                return last
            if not wait or time.time() >= deadline:
                return last
            poll_count += 1
            remaining = deadline - time.time()
            if remaining <= 0:
                raise ProviderBlocked("lechuang", "video generation wait exceeded 20 minutes", details={"retryable": True, "provider_task_id": video_id})
            self._sleep(min(VIDEO_POLL_SECONDS, remaining))
        raise ProviderBlocked("lechuang", "video generation wait exceeded 20 minutes", details={"retryable": True, "provider_task_id": video_id})

    def _materialize_video(self, task: ProviderTask) -> ProviderTask:
        if task.result.get("asset") is not None:
            return task
        video_id = task.provider_task_id
        content = self._http(
            "GET",
            VIDEO_CONTENT_ENDPOINT.format(video_id=quote(video_id, safe="")),
            timeout=VIDEO_CONTENT_TIMEOUT_SECONDS,
            binary=True,
        )
        if not isinstance(content, (bytes, bytearray)):
            raise ProviderBlocked("lechuang", "video content is not binary")
        inspect_video_bytes(bytes(content))
        width = height = 0
        duration = float((task.result or {}).get("seconds") or 0)
        mime = "video/mp4"
        tmp = Path(self.asset_root or "/tmp") / f"lechuang-video-{video_id}.mp4"
        try:
            from creative.render.ffmpeg import video_info
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(bytes(content))
            info = video_info(tmp)
            width = int(info.get("width") or 0)
            height = int(info.get("height") or 0)
            duration = float(info.get("duration") or duration)
            mime = str(info.get("mime") or mime)
        except Exception:
            pass
        finally:
            tmp.unlink(missing_ok=True)
        payload = task.result or {}
        asset = persist_bytes(
            bytes(content),
            asset_type="video",
            suffix=".mp4",
            root=self.asset_root,
            mime_type=mime,
            width=width or None,
            height=height or None,
            duration=duration or None,
            workflow_id=payload.get("workflow_id"),
            workflow_version=payload.get("workflow_version"),
            creative_run_id=payload.get("run_id"),
            prompt_id=payload.get("prompt_id"),
            character_id=payload.get("character_id"),
            account_id=payload.get("account_id"),
            series_id=payload.get("series_id"),
            episode_id=payload.get("episode_id"),
            content_package_id=payload.get("content_package_id"),
            creative_context_id=payload.get("creative_context_id"),
            world_id=payload.get("world_id"),
            provider="xiaole-lechuang",
            provider_task_id=video_id,
            model=str(payload.get("model") or ""),
            generation_mode="PROVIDER_API",
            tool="lechuang",
            source_asset_id=payload.get("source_asset_id"),
            metadata={
                "provider": "xiaole",
                "service": "lechuang",
                "provider_task_id": video_id,
                "model": payload.get("model"),
                "seconds": payload.get("seconds"),
                "size": payload.get("size"),
                "aspect_ratio": payload.get("aspect_ratio"),
                "source": "xiaole-lechuang",
                "source_url": payload.get("source_url") or "",
                "created_at": utcnow(),
            },
        )
        qa = TechnicalQA().inspect_video(asset)
        if qa.get("decision") != "pass":
            raise ProviderBlocked("lechuang", "technical qa failed", details={"qa": qa})
        result = {
            **payload,
            "asset": asset,
            "asset_id": asset.asset_id,
            "path": asset.path,
            "sha256": asset.sha256,
            "mime_type": mime,
            "byte_size": asset.size,
            "width": asset.width,
            "height": asset.height,
            "duration": asset.duration,
            "provider_artifact_id": video_id,
            "qa": qa,
        }
        completed = ProviderTask(
            provider="lechuang",
            provider_task_id=video_id,
            status="succeeded",
            kind=task.kind,
            result=result,
            poll_count=task.poll_count,
        )
        self._tasks[video_id] = completed
        return completed

    def _reference_files(self, payload: dict[str, Any]) -> list[tuple[str, str, bytes, str]]:
        files: list[tuple[str, str, bytes, str]] = []
        raw_items = payload.get("input_reference") or payload.get("references") or []
        if payload.get("source_path"):
            raw_items = list(raw_items) + [payload.get("source_path")]
        source_bytes = payload.get("source_bytes")
        if source_bytes:
            files.append(("input_reference[]", "reference.png", bytes(source_bytes), "image/png"))
        for item in raw_items:
            path = Path(str(item))
            if not path.is_file():
                raise ProviderBlocked("lechuang", f"reference image missing: {path}")
            data = path.read_bytes()
            mime = "image/png"
            if data.startswith(b"\xff\xd8\xff"):
                mime = "image/jpeg"
            files.append(("input_reference[]", path.name, data, mime))
        return files

    def upload_asset(self, payload: dict[str, Any]) -> Any:
        raise UnsupportedCapability("upload_asset", provider="lechuang")

    def handle_rate_limit(self, status_code: int, headers: dict[str, str] | None = None) -> None:
        if int(status_code) != 429:
            return
        retry_after = None
        if headers:
            raw = headers.get("Retry-After") or headers.get("retry-after")
            if raw:
                try:
                    retry_after = float(raw)
                except ValueError:
                    retry_after = None
        raise RateLimited("lechuang", retry_after=retry_after)

    def backoff_for(self, poll_count: int) -> float:
        index = min(max(poll_count, 0), len(self.backoff_seconds) - 1)
        return float(self.backoff_seconds[index])
