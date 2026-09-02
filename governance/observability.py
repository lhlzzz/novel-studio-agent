"""Structured request logs. Secrets never enter log output."""

from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

SECRET_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "token",
    "access_token",
    "refresh_token",
    "cookie",
    "secret",
    "password",
    "client_secret",
    "session",
    "scrapecreators_api_key",
    "lechuang_api_key",
}
SECRET_PATTERN = re.compile(
    r"(api[_-]?key|authorization|bearer|refresh[_-]?token|access[_-]?token|cookie|secret)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def new_request_id() -> str:
    return uuid.uuid4().hex


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[redacted]" if str(key).lower() in SECRET_KEYS else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[redacted]", value)
    return value


def log_event(
    *,
    agent: str,
    action: str,
    status: str,
    request_id: str = "",
    job_id: str = "",
    provider: str = "",
    integration_id: str = "",
    account_id: str = "",
    error_code: str | None = None,
    duration_ms: int | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "agent": agent,
        "action": action,
        "job_id": job_id,
        "provider": provider,
        "integration_id": integration_id or account_id,
        "account_id": account_id or integration_id,
        "status": status,
        "error_code": error_code,
        "duration_ms": duration_ms,
    }
    payload.update(extra)
    payload = redact(payload)
    print(json.dumps(payload, default=str), flush=True)
    return payload


class Timer:
    def __init__(self) -> None:
        self.started = time.perf_counter()

    def duration_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)
