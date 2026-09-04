"""Xiaole / Lechuang HTTP owner. Image uses the verified OpenAI-compatible contract."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
SUPPORTED_MODELS = {
    "gpt-image-2",
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
}
SUPPORTED_SIZES = {"512", "1K", "2K", "4K"}
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_IMAGE_SIZE = "2K"
DEFAULT_ASPECT_RATIO = "9:16"
IMAGE_TIMEOUT_SECONDS = 600
MAX_POLL_COUNT = 30
MAX_WAIT_SECONDS = 180
BACKOFF_SECONDS = (1, 2, 4, 8, 15)
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
UNVERIFIED_KINDS = frozenset({
    "edit_image",
    "image_to_image",
    "generate_video",
    "text_to_video",
    "video_generation",
    "extend_video",
    "video_extend",
    "edit_video",
    "video_edit",
    "image_to_video",
    "upload_asset",
})
VIDEO_NOT_VERIFIED = "XiaoleAI/Lechuang video API is not present in repository evidence"


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
        self.contract_reason = "XiaoleAI OpenAI-compatible image API (/images/generations, b64_json)"
        self.video_reason = VIDEO_NOT_VERIFIED
        self.max_poll_count = MAX_POLL_COUNT
        self.max_wait_seconds = MAX_WAIT_SECONDS
        self.backoff_seconds = BACKOFF_SECONDS
        self.asset_root = asset_root
        self._tasks: dict[str, ProviderTask] = {}
        self._idempotency: dict[str, str] = {}

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

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _http(self, method: str, path: str, **kwargs: Any) -> Any:
        timeout = float(kwargs.pop("timeout", 30))
        url = path if str(path).startswith("http") else f"{self.base_url}{path}"
        payload = kwargs.get("json")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=data, headers=self._headers(), method=method.upper())
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    raise ProviderBlocked("lechuang", "missing result")
                try:
                    body = json.loads(raw)
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
        if kind in UNVERIFIED_KINDS or kind not in IMAGE_KINDS:
            raise UnsupportedCapability(kind, provider="lechuang")
        return self.generate_image(payload)

    def get_task(self, provider_task_id: str) -> ProviderTask:
        task = self._tasks.get(provider_task_id)
        if task is None:
            raise ProviderBlocked("lechuang", "provider task not found")
        return task

    def cancel_task(self, provider_task_id: str) -> ProviderTask:
        task = self.get_task(provider_task_id)
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
        if mime != MIME_BY_SUFFIX.get(suffix, mime):
            mime = MIME_BY_SUFFIX.get(suffix, mime)
        request_id = str(body.get("request_id") or body.get("id") or "")
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
            metadata={
                "provider": "xiaole",
                "service": "lechuang",
                "provider_task_id": request_id,
                "model": str(body.get("model") or model),
                "image_size": image_size,
                "aspect_ratio": aspect_ratio,
                "source": "xiaole-lechuang",
                "created_at": utcnow(),
                "account_id": (payload or {}).get("account_id"),
                "series_id": (payload or {}).get("series_id"),
                "episode_id": (payload or {}).get("episode_id"),
                "creative_context_id": (payload or {}).get("creative_context_id"),
            },
        )
        qa = TechnicalQA().inspect_image(asset)
        if qa.get("decision") != "pass":
            raise ProviderBlocked("lechuang", "technical qa failed", details={"qa": qa})
        task_id = request_id or asset.sha256
        result = {
            "asset": asset,
            "asset_id": asset.asset_id,
            "credits_actual": 1.0,
            "request_id": request_id,
            "qa": qa,
            "model": str(body.get("model") or model),
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
