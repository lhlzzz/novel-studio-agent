"""xAI video HTTP owner. Model is grok-imagine-video-1.5, never Grok 4.6."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from creative.assets import persist_bytes
from creative.errors import AuthError, ProviderBlocked, RateLimited, UnsupportedCapability
from creative.judges.technical import TechnicalQA
from creative.providers.xai.credentials import API_KEY_ENV, BASE_URL_ENV, load_xai_credential
from creative.providers.xai.schemas import XAIAuth
from creative.schemas import ProviderTask, utcnow

VIDEO_MODEL = "grok-imagine-video-1.5"
SUBMIT_ENDPOINT = "/videos/generations"
POLL_ENDPOINT = "/videos/{request_id}"
DEFAULT_DURATION = 6
DEFAULT_ASPECT_RATIO = "9:16"
VIDEO_TIMEOUT_SECONDS = 30
POLL_TIMEOUT_SECONDS = 30
DOWNLOAD_TIMEOUT_SECONDS = 120
MAX_POLL_COUNT = 30
MAX_WAIT_SECONDS = 180
BACKOFF_SECONDS = (1, 2, 4, 8, 15)
VIDEO_CONTRACT_VERIFIED = False
VIDEO_NOT_VERIFIED = (
    "xAI grok-imagine-video-1.5 contract is implemented but not live-verified; "
    "REAL_VIDEO_E2E stays NOT_VERIFIED until a real API MediaAsset + TechnicalQA exist"
)
VIDEO_KINDS = frozenset({
    "generate_video",
    "text_to_video",
    "video_generation",
    "image_to_video",
})
UNVERIFIED_KINDS = frozenset({
    "extend_video",
    "video_extend",
    "edit_video",
    "video_edit",
    "generate_image",
    "text_to_image",
    "image_generation",
    "edit_image",
    "image_to_image",
    "upload_asset",
})


def parse_error_payload(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        for key in ("message", "detail"):
            if payload.get(key):
                return str(payload[key])
    return fallback


class XAIVideoClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        *,
        asset_root=None,
    ) -> None:
        self.credential = load_xai_credential(api_key=api_key, base_url=base_url)
        self.base_url = self.credential.endpoint
        self.api_key = self.credential.api_key
        self.contract_verified = VIDEO_CONTRACT_VERIFIED
        self.video_contract_verified = VIDEO_CONTRACT_VERIFIED
        self.contract_reason = VIDEO_NOT_VERIFIED
        self.video_reason = VIDEO_NOT_VERIFIED
        self.model = VIDEO_MODEL
        self.max_poll_count = MAX_POLL_COUNT
        self.max_wait_seconds = MAX_WAIT_SECONDS
        self.backoff_seconds = BACKOFF_SECONDS
        self.asset_root = asset_root
        self._tasks: dict[str, ProviderTask] = {}
        self._idempotency: dict[str, str] = {}

    def auth(self) -> XAIAuth:
        ready, reason = self.live_ready()
        return XAIAuth(
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

    def map_http_error(self, status_code: int, body: str = "", headers: dict[str, str] | None = None) -> None:
        if int(status_code) in {401, 403}:
            raise AuthError("xAI authentication failed", provider="xai")
        if int(status_code) == 429:
            self.handle_rate_limit(status_code, headers)
        if int(status_code) >= 500:
            raise ProviderBlocked("xai", f"provider failure HTTP {status_code}", details={"retryable": True, "body": body[:300]})
        raise ProviderBlocked("xai", f"invalid response HTTP {status_code}", details={"body": body[:300]})

    def _require_ready(self) -> None:
        ready, reason = self.live_ready()
        if ready:
            return
        if API_KEY_ENV in reason:
            raise AuthError(reason, provider="xai")
        raise ProviderBlocked("xai", reason)

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _http(self, method: str, path: str, **kwargs: Any) -> Any:
        timeout = float(kwargs.pop("timeout", VIDEO_TIMEOUT_SECONDS))
        url = path if str(path).startswith("http") else f"{self.base_url}{path}"
        payload = kwargs.get("json")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=data, headers=self._headers(), method=method.upper())
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                content_type = ""
                try:
                    content_type = str(response.headers.get("Content-Type") or "")
                except Exception:
                    content_type = ""
                if kwargs.get("raw"):
                    return raw, content_type
                text = raw.decode("utf-8") if raw else ""
                if not text:
                    raise ProviderBlocked("xai", "missing result")
                try:
                    body = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ProviderBlocked("xai", "invalid response") from exc
                if isinstance(body, dict) and body.get("error"):
                    raise ProviderBlocked("xai", parse_error_payload(body, "provider error"))
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
            raise ProviderBlocked("xai", f"invalid response HTTP {exc.code}: {message}")
        except TimeoutError as exc:
            raise ProviderBlocked("xai", "HTTP timeout", details={"retryable": True}) from exc
        except URLError as exc:
            raise ProviderBlocked("xai", f"provider failure: {exc.reason}", details={"retryable": True}) from exc

    def submit_video(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_ready()
        prompt = str((payload or {}).get("prompt") or "").strip()
        if not prompt:
            raise ProviderBlocked("xai", "prompt is required")
        model = str((payload or {}).get("model") or VIDEO_MODEL).strip() or VIDEO_MODEL
        if model != VIDEO_MODEL:
            raise ProviderBlocked("xai", f"unsupported video model: {model}")
        duration = payload.get("duration_seconds")
        if duration is None:
            duration = DEFAULT_DURATION
        duration = float(duration)
        if duration not in {6.0, 10.0} and duration not in {6, 10}:
            duration = DEFAULT_DURATION
        aspect_ratio = str((payload or {}).get("aspect_ratio") or DEFAULT_ASPECT_RATIO).strip() or DEFAULT_ASPECT_RATIO
        body: dict[str, Any] = {
            "model": VIDEO_MODEL,
            "prompt": prompt,
            "duration": int(duration),
            "aspect_ratio": aspect_ratio,
        }
        source_url = str((payload or {}).get("source_url") or (payload or {}).get("image_url") or "").strip()
        if not source_url:
            reference = (payload or {}).get("reference")
            if isinstance(reference, str) and reference.startswith("http"):
                source_url = reference
        if source_url:
            body["image_url"] = source_url
        return self._http("POST", SUBMIT_ENDPOINT, json=body, timeout=VIDEO_TIMEOUT_SECONDS)

    def poll_video(self, request_id: str) -> dict[str, Any]:
        self._require_ready()
        if not str(request_id or "").strip():
            raise ProviderBlocked("xai", "request_id is required")
        path = POLL_ENDPOINT.format(request_id=request_id)
        return self._http("GET", path, timeout=POLL_TIMEOUT_SECONDS)

    def download_video(self, url: str) -> bytes:
        self._require_ready()
        if not str(url or "").startswith("http"):
            raise ProviderBlocked("xai", "video url missing")
        raw, content_type = self._http("GET", url, timeout=DOWNLOAD_TIMEOUT_SECONDS, raw=True)
        if not raw:
            raise ProviderBlocked("xai", "downloaded video is empty")
        if content_type and "json" in content_type and raw[:1] in {b"{", b"["}:
            raise ProviderBlocked("xai", "video url returned JSON, not media")
        return raw

    def create_task(self, kind: str, payload: dict[str, Any]) -> ProviderTask:
        if kind in UNVERIFIED_KINDS or kind not in VIDEO_KINDS:
            raise UnsupportedCapability(kind, provider="xai")
        return self.generate_video(payload)

    def get_task(self, provider_task_id: str) -> ProviderTask:
        task = self._tasks.get(provider_task_id)
        if task is None:
            raise ProviderBlocked("xai", "provider task not found")
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

    def generate_video(self, payload: dict[str, Any]) -> ProviderTask:
        self._require_ready()
        key = str((payload or {}).get("idempotency_key") or "")
        if key and key in self._idempotency:
            return self.get_task(self._idempotency[key])
        submitted = self.submit_video(payload)
        if not isinstance(submitted, dict):
            raise ProviderBlocked("xai", "invalid submit schema")
        request_id = str(submitted.get("request_id") or submitted.get("id") or submitted.get("video_id") or "")
        if not request_id:
            raise ProviderBlocked("xai", "submit response missing request_id")
        started = time.monotonic()
        poll_count = 0
        body = submitted
        while True:
            status = str(body.get("status") or body.get("state") or "").lower()
            if status in {"succeeded", "completed", "complete", "done", "success"}:
                break
            if status in {"failed", "error", "cancelled", "canceled"}:
                raise ProviderBlocked("xai", parse_error_payload(body, f"video {status}"))
            if poll_count >= self.max_poll_count or (time.monotonic() - started) > self.max_wait_seconds:
                raise ProviderBlocked("xai", "video poll timeout", details={"retryable": True, "request_id": request_id})
            time.sleep(self.backoff_for(poll_count))
            poll_count += 1
            body = self.poll_video(request_id)
            if not isinstance(body, dict):
                raise ProviderBlocked("xai", "invalid poll schema")
        video_url = str(
            body.get("url")
            or body.get("video_url")
            or ((body.get("data") or {}) if isinstance(body.get("data"), dict) else {}).get("url")
            or ""
        )
        if not video_url and isinstance(body.get("data"), list) and body["data"]:
            first = body["data"][0]
            if isinstance(first, dict):
                video_url = str(first.get("url") or first.get("video_url") or "")
        if not video_url:
            raise ProviderBlocked("xai", "completed video missing url")
        video_bytes = self.download_video(video_url)
        if not video_bytes:
            raise ProviderBlocked("xai", "downloaded video is empty")
        duration = payload.get("duration_seconds") or body.get("duration") or DEFAULT_DURATION
        asset = persist_bytes(
            video_bytes,
            asset_type="video",
            suffix=".mp4",
            root=self.asset_root,
            mime_type="video/mp4",
            duration=float(duration or 0) or None,
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
            provider="xai",
            provider_task_id=request_id,
            model=VIDEO_MODEL,
            metadata={
                "provider": "xai",
                "service": "video",
                "provider_task_id": request_id,
                "model": VIDEO_MODEL,
                "aspect_ratio": (payload or {}).get("aspect_ratio") or DEFAULT_ASPECT_RATIO,
                "source_asset_id": (payload or {}).get("source_asset_id"),
                "source_url": (payload or {}).get("source_url") or (payload or {}).get("image_url"),
                "created_at": utcnow(),
                "account_id": (payload or {}).get("account_id"),
                "series_id": (payload or {}).get("series_id"),
                "episode_id": (payload or {}).get("episode_id"),
                "creative_context_id": (payload or {}).get("creative_context_id"),
            },
        )
        qa = TechnicalQA().inspect_video(asset)
        if qa.get("decision") != "pass":
            raise ProviderBlocked("xai", "technical qa failed", details={"qa": qa})
        result = {
            "asset": asset,
            "asset_id": asset.asset_id,
            "credits_actual": 8.0,
            "request_id": request_id,
            "qa": qa,
            "model": VIDEO_MODEL,
            "source_asset_id": (payload or {}).get("source_asset_id"),
            "workflow_id": (payload or {}).get("workflow_id"),
        }
        if key:
            result["idempotency_key"] = key
        task = ProviderTask(
            provider="xai",
            provider_task_id=request_id,
            status="succeeded",
            kind="generate_video",
            result=result,
            poll_count=poll_count,
        )
        self._tasks[request_id] = task
        if key:
            self._idempotency[key] = request_id
        return task

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
        raise RateLimited("xai", retry_after=retry_after)

    def backoff_for(self, poll_count: int) -> float:
        index = min(max(poll_count, 0), len(self.backoff_seconds) - 1)
        return float(self.backoff_seconds[index])
