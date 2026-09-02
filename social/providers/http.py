"""Shared HTTP owner for native social providers. Tokens are never logged."""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from governance.observability import log_event, new_request_id, redact
from social.providers.errors import NetworkError, TimeoutError as SocialTimeoutError, classify_http_error

RETRYABLE = (NetworkError, SocialTimeoutError)


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
        self.rate_limit: dict[str, Any] = {"remaining": None, "reset_at": None}

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
    ) -> Any:
        request_id = request_id or new_request_id()
        url = path if absolute or path.startswith("http") else f"{self.base_url}{path}"
        if query:
            url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})}"
        payload = data
        hdrs = {key: value for key, value in (headers or {}).items() if value}
        hdrs.setdefault("User-Agent", "MeitiSocial/4.4")
        hdrs["X-Request-Id"] = request_id
        if idempotency_key:
            hdrs["Idempotency-Key"] = idempotency_key
        if json_body is not None:
            payload = json.dumps(json_body).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        elif content_type and payload is not None:
            hdrs.setdefault("Content-Type", content_type)
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
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
                    path=path,
                    attempt=attempt,
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
                    path=path,
                    attempt=attempt,
                    error_code=exc.__class__.__name__,
                    error_message=str(redact(str(exc))),
                )
                if not retryable or attempt >= self.max_attempts:
                    raise
                delay = min(2 ** (attempt - 1), 8)
                if getattr(exc, "retry_after", None):
                    delay = float(exc.retry_after)
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
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {"raw": raw.decode("utf-8", "replace")}

    def _capture_rate_limit(self, headers: Any) -> None:
        if headers is None:
            return
        remaining = headers.get("x-rate-limit-remaining") or headers.get("X-Rate-Limit-Remaining")
        reset_at = headers.get("x-rate-limit-reset") or headers.get("X-Rate-Limit-Reset")
        if remaining is not None:
            try:
                self.rate_limit["remaining"] = int(remaining)
            except ValueError:
                self.rate_limit["remaining"] = remaining
        if reset_at is not None:
            self.rate_limit["reset_at"] = reset_at
