"""Shared HTTP owner for native social providers. Tokens are never logged."""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from governance.observability import log_event, new_request_id, redact
from social.providers.errors import NetworkError, TimeoutError as SocialTimeoutError, classify_http_error

REDACT_HEADERS = {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-access-token"}


class SocialHttpClient:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        timeout: float = 20.0,
        max_attempts: int = 3,
        opener: Any | None = None,
        sleeper: Any | None = None,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_attempts = max_attempts
        self._opener = opener
        self._sleeper = sleeper or time.sleep
        self.rate_limit: dict[str, Any] = {"remaining": None, "reset_at": None, "retry_after": None}

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        query: dict[str, Any] | None = None,
        json_body: Any | None = None,
        data: bytes | None = None,
        content_type: str | None = None,
        request_id: str = "",
        distribution_job_id: str = "",
        account_id: str = "",
        idempotency_key: str = "",
        absolute: bool = False,
        retry: bool | None = None,
        extra_headers: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> Any:
        request_id = request_id or new_request_id()
        url = path if absolute or path.startswith("http") else f"{self.base_url}{path}"
        if query:
            url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})}"
        payload = data
        hdrs = {key: value for key, value in (headers or {}).items() if value}
        if extra_headers:
            hdrs.update({key: value for key, value in extra_headers.items() if value})
        hdrs.setdefault("User-Agent", "MeitiSocial/4.4.3")
        hdrs["X-Request-Id"] = request_id
        if idempotency_key:
            hdrs.setdefault("Idempotency-Key", idempotency_key)
        if files:
            payload, content = _encode_multipart(json_body if isinstance(json_body, dict) else {}, files)
            hdrs["Content-Type"] = content
        elif json_body is not None:
            payload = json.dumps(json_body).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        elif content_type and payload is not None:
            hdrs.setdefault("Content-Type", content_type)
        method_u = method.upper()
        if retry is None:
            retry = method_u in {"GET", "HEAD", "OPTIONS"}
        attempts = self.max_attempts if retry else 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            try:
                body = self._send(method, url, hdrs, payload)
                log_event(
                    agent="social-provider",
                    action=method.lower(),
                    status="ok",
                    request_id=request_id,
                    job_id=distribution_job_id,
                    provider=self.provider,
                    account_id=account_id,
                    path=_safe_path(path),
                    attempt=attempt,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    endpoint_path=_safe_path(path),
                )
                return body
            except Exception as exc:
                last_error = exc
                retryable = bool(getattr(exc, "retryable", False))
                log_event(
                    agent="social-provider",
                    action=method.lower(),
                    status="error",
                    request_id=request_id,
                    job_id=distribution_job_id,
                    provider=self.provider,
                    account_id=account_id,
                    path=_safe_path(path),
                    attempt=attempt,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    endpoint_path=_safe_path(path),
                    error_code=exc.__class__.__name__,
                    http_status=getattr(exc, "http_status", None),
                    error_message=str(redact(str(exc))),
                )
                if not retryable or attempt >= attempts:
                    raise
                delay = min(2 ** (attempt - 1), 8)
                if getattr(exc, "retry_after", None):
                    delay = float(exc.retry_after)
                    self.rate_limit["retry_after"] = delay
                self._sleeper(delay)
        raise last_error or NetworkError(f"{self.provider} {method} {path} failed")

    def _send(self, method: str, url: str, headers: dict[str, str], data: bytes | None) -> Any:
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        opener = self._opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )
        try:
            with opener.open(req, timeout=self.timeout) as response:
                self._capture_rate_limit(getattr(response, "headers", None))
                raw = response.read()
                location = response.headers.get("Location") if getattr(response, "headers", None) else None
        except urllib.error.HTTPError as exc:
            self._capture_rate_limit(getattr(exc, "headers", None))
            detail = exc.read().decode("utf-8", "replace")
            retry_after = None
            if exc.headers and exc.headers.get("Retry-After"):
                try:
                    retry_after = float(exc.headers.get("Retry-After"))
                except ValueError:
                    retry_after = None
            raise classify_http_error(int(exc.code), f"{self.provider} {method} failed ({exc.code}): {detail}", retry_after)
        except SocialTimeoutError as exc:
            raise SocialTimeoutError(f"{self.provider} {method} timed out: {exc}") from exc
        except Exception as exc:
            name = exc.__class__.__name__.lower()
            if "time" in name:
                raise SocialTimeoutError(f"{self.provider} {method} timed out: {exc}") from exc
            raise NetworkError(f"{self.provider} {method} failed: {exc}") from exc
        if not raw:
            return {"headers": {"location": location}} if location else {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
            if location and isinstance(parsed, dict) and "headers" not in parsed:
                parsed = dict(parsed)
                parsed.setdefault("headers", {"location": location})
            return parsed
        except json.JSONDecodeError:
            payload = {"raw": raw.decode("utf-8", "replace")}
            if location:
                payload["headers"] = {"location": location}
            return payload

    def _capture_rate_limit(self, headers: Any) -> None:
        if headers is None:
            return
        remaining = headers.get("x-rate-limit-remaining") or headers.get("X-Rate-Limit-Remaining")
        reset_at = headers.get("x-rate-limit-reset") or headers.get("X-Rate-Limit-Reset")
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
        if remaining is not None:
            try:
                self.rate_limit["remaining"] = int(remaining)
            except ValueError:
                self.rate_limit["remaining"] = remaining
        if reset_at is not None:
            self.rate_limit["reset_at"] = reset_at
        if retry_after is not None:
            self.rate_limit["retry_after"] = retry_after


def _safe_path(path: str) -> str:
    parsed = urllib.parse.urlparse(path)
    return parsed.path or path


def _encode_multipart(fields: dict[str, Any], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    boundary = f"meiti{int(time.time() * 1000)}"
    chunks: list[bytes] = []
    for key, value in (fields or {}).items():
        if value is None:
            continue
        chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode("utf-8"))
    for key, (filename, data, mime) in files.items():
        header = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8")
        chunks.append(header + data + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"
