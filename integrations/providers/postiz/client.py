"""Single HTTP client owner for the Postiz Public API."""

from __future__ import annotations

import json
import mimetypes
import os
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

from integrations.contracts.distribution import ProviderHealth
from integrations.providers.postiz.errors import (
    NetworkError,
    PostizClientError,
    PostizTimeoutError,
    RateLimitError,
    classify_http_error,
)

__all__ = ["PostizClient", "PostizClientError"]


class PostizClient:
    """Own URL, authentication, serialization, and all Postiz HTTP calls."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        *,
        timeout: float = 30.0,
        max_attempts: int = 3,
        sleeper: Callable[[float], None] | None = None,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("POSTIZ_API_URL") or "http://127.0.0.1:4007"
        ).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("POSTIZ_API_KEY", "")
        self.timeout = timeout
        self.max_attempts = max(1, int(max_attempts))
        self._sleep = sleeper or time.sleep
        # Postiz is operator-owned local infrastructure. Never send it through HTTP_PROXY.
        self._opener = opener or build_opener(ProxyHandler({})).open
        self._request_context_id: ContextVar[str] = ContextVar("postiz_request_id", default="")

    @contextmanager
    def request_context(self, request_id: str):
        token = self._request_context_id.set(request_id or "")
        try:
            yield
        finally:
            self._request_context_id.reset(token)

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = self.api_key
        headers.update(extra or {})
        return headers

    def _retry_after(self, headers: Any) -> float | None:
        if headers is None:
            return None
        raw = headers.get("Retry-After") if hasattr(headers, "get") else None
        if raw is None:
            return None
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            return None

    def _classify(self, exc: Exception, method: str, path: str) -> PostizClientError:
        if isinstance(exc, TimeoutError):
            return PostizTimeoutError(f"Postiz {method} {path} failed (timeout): {exc}")
        if isinstance(exc, HTTPError):
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")
            except Exception:
                body = ""
            detail = body or getattr(exc, "reason", None) or str(exc)
            retry_after = self._retry_after(getattr(exc, "headers", None))
            classified = classify_http_error(int(exc.code), f"Postiz {method} {path} failed ({exc.code}): {detail}", retry_after)
            return classified
        if isinstance(exc, URLError):
            return NetworkError(f"Postiz {method} {path} failed (network): {getattr(exc, 'reason', exc)}")
        return NetworkError(f"Postiz {method} {path} failed: {exc}")

    def _send(self, request: Request, *, method: str, path: str, timeout: float) -> Any:
        attempts = self.max_attempts
        last_error: PostizClientError | None = None
        for attempt in range(1, attempts + 1):
            try:
                with self._opener(request, timeout=timeout) as response:
                    raw = response.read()
                return self._decode(raw, method, path)
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                last_error = self._classify(exc, method, path)
                retryable = bool(getattr(last_error, "retryable", False))
                if not retryable or attempt >= attempts:
                    raise last_error from exc
                delay = 0.5 * (2 ** (attempt - 1))
                if isinstance(last_error, RateLimitError) and last_error.retry_after is not None:
                    delay = last_error.retry_after
                self._sleep(delay)
        raise last_error or NetworkError(f"Postiz {method} {path} failed")

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        request_id: str | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            values = {key: value for key, value in query.items() if value is not None}
            if values:
                url = f"{url}?{urlencode(values)}"
        request_headers = self._headers({"Content-Type": "application/json"})
        request_headers["X-Request-ID"] = request_id or self._request_context_id.get() or uuid.uuid4().hex
        request_headers.update(headers or {})
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=data, headers=request_headers, method=method)
        return self._send(request, method=method, path=path, timeout=self.timeout)

    @staticmethod
    def _decode(raw: bytes, method: str, path: str) -> Any:
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise PostizClientError(f"Postiz {method} {path} returned invalid JSON") from exc

    def health(self) -> ProviderHealth:
        try:
            connected = self.is_connected()
            integrations = self.list_integrations()
            from integrations.providers.postiz.schemas import unwrap_data
            items = unwrap_data(integrations)
            count = len(items) if isinstance(items, list) else 0
            return ProviderHealth(
                provider="postiz",
                reachable=True,
                authenticated=bool(connected),
                account_count=count,
                last_error=None,
                rate_limit_state="ok",
            )
        except PostizClientError as exc:
            return ProviderHealth(
                provider="postiz",
                reachable=not isinstance(exc, NetworkError),
                authenticated=False,
                last_error=str(exc),
                rate_limit_state="error",
            )

    def is_connected(self, *, request_id: str | None = None) -> bool:
        raw = self._request("/public/v1/is-connected", request_id=request_id)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, dict):
            for key in ("connected", "isConnected", "data"):
                value = raw.get(key)
                if isinstance(value, bool):
                    return value
            return bool(raw)
        return bool(raw)

    def list_integrations(self, group: str | None = None, *, request_id: str | None = None) -> Any:
        return self._request("/public/v1/integrations", query={"group": group}, request_id=request_id)

    def get_integration_settings(self, integration_id: str, *, request_id: str | None = None) -> Any:
        return self._request(f"/public/v1/integration-settings/{integration_id}", request_id=request_id)

    def get_settings(self, integration_id: str, *, request_id: str | None = None) -> Any:
        return self.get_integration_settings(integration_id, request_id=request_id)

    def create_post(self, payload: dict[str, Any], *, request_id: str | None = None) -> Any:
        return self._request("/public/v1/posts", method="POST", payload=payload, request_id=request_id)

    def list_posts(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        request_id: str | None = None,
    ) -> Any:
        return self._request(
            "/public/v1/posts",
            query={"startDate": start_date, "endDate": end_date},
            request_id=request_id,
        )

    def delete_post(self, post_id: str, *, request_id: str | None = None) -> Any:
        return self._request(f"/public/v1/posts/{post_id}", method="DELETE", request_id=request_id)

    def upload_media(self, file_path: str | Path, *, request_id: str | None = None) -> Any:
        path = Path(file_path)
        if not path.is_file():
            raise PostizClientError(f"media file does not exist: {path}")
        boundary = f"----meiti-{uuid.uuid4().hex}"
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        content = path.read_bytes()
        body = b"--" + boundary.encode() + b"\r\n"
        body += (
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        ).encode()
        body += f"Content-Type: {content_type}\r\n\r\n".encode()
        body += content + b"\r\n--" + boundary.encode() + b"--\r\n"
        headers = self._headers({
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "X-Request-ID": request_id or self._request_context_id.get() or uuid.uuid4().hex,
        })
        request = Request(
            f"{self.base_url}/public/v1/upload",
            data=body,
            headers=headers,
            method="POST",
        )
        return self._send(request, method="POST", path="/public/v1/upload", timeout=max(self.timeout, 60.0))

    def get_post_analytics(self, post_id: str, days: int = 7, *, request_id: str | None = None) -> Any:
        return self._request(
            f"/public/v1/analytics/post/{post_id}", query={"date": days}, request_id=request_id
        )

    def get_integration_analytics(self, integration_id: str, days: int = 30, *, request_id: str | None = None) -> Any:
        return self._request(
            f"/public/v1/analytics/{integration_id}", query={"date": days}, request_id=request_id
        )

    def trigger_integration_tool(
        self,
        integration_id: str,
        method_name: str,
        data: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> Any:
        return self._request(
            f"/public/v1/integration-trigger/{integration_id}",
            method="POST",
            payload={"methodName": method_name, "data": data or {}},
            request_id=request_id,
        )

    def get_status(self, provider_post_id: str, *, request_id: str | None = None) -> Any:
        posts = self.list_posts(request_id=request_id)
        if isinstance(posts, dict) and isinstance(posts.get("data"), list):
            posts = posts["data"]
        if isinstance(posts, list):
            return next((post for post in posts if str(post.get("id")) == str(provider_post_id)), {
                "id": provider_post_id,
                "status": "UNKNOWN",
            })
        return {"id": provider_post_id, "status": "UNKNOWN"}

    def trigger_tool(self, integration_id: str, method_name: str, data: dict[str, Any] | None = None, *, request_id: str | None = None) -> Any:
        return self.trigger_integration_tool(integration_id, method_name, data, request_id=request_id)
