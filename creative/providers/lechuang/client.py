"""HTTP owner for Lechuang. Endpoints are not guessed; live traffic stays blocked."""

from __future__ import annotations

import os
import time
from typing import Any

from creative.errors import AuthError, ProviderBlocked, RateLimited, UnsupportedCapability
from creative.providers.lechuang.capabilities import load_models
from creative.providers.lechuang.schemas import LechuangAuth

CONTRACT_VERIFIED = False
MAX_POLL_COUNT = 30
MAX_WAIT_SECONDS = 180
BACKOFF_SECONDS = (1, 2, 4, 8, 15)


class LechuangClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        models = load_models()
        contract = models.get("contract") or {}
        self.contract_verified = bool(contract.get("verified")) and CONTRACT_VERIFIED
        self.contract_reason = str(contract.get("reason") or "Lechuang API contract unverified")
        env_url = os.getenv("LECHUANG_API_URL", "").strip()
        self.base_url = (base_url if base_url is not None else env_url).rstrip("/")
        key = api_key if api_key is not None else os.getenv("LECHUANG_API_KEY", "")
        self.api_key = str(key or "")
        self.max_poll_count = MAX_POLL_COUNT
        self.max_wait_seconds = MAX_WAIT_SECONDS
        self.backoff_seconds = BACKOFF_SECONDS

    def auth(self) -> LechuangAuth:
        ready, reason = self.live_ready()
        return LechuangAuth(
            base_url=self.base_url,
            api_key_present=bool(self.api_key.strip()),
            contract_verified=self.contract_verified,
            reason="" if ready else reason,
        )

    def live_ready(self) -> tuple[bool, str]:
        if not self.api_key.strip():
            return False, "LECHUANG_API_KEY missing"
        if not self.base_url:
            return False, "LECHUANG_API_URL missing"
        if not self.contract_verified:
            return False, self.contract_reason
        return True, "ok"

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        ready, reason = self.live_ready()
        if not ready:
            if "LECHUANG_API_KEY" in reason:
                raise AuthError(reason, provider="lechuang")
            raise ProviderBlocked("lechuang", reason)
        raise UnsupportedCapability(f"{method} {path}", provider="lechuang")

    def create_task(self, kind: str, payload: dict[str, Any]) -> Any:
        return self.request("POST", "/tasks", json={"kind": kind, "payload": payload})

    def get_task(self, provider_task_id: str) -> Any:
        return self.request("GET", f"/tasks/{provider_task_id}")

    def cancel_task(self, provider_task_id: str) -> Any:
        return self.request("POST", f"/tasks/{provider_task_id}/cancel")

    def get_result(self, provider_task_id: str) -> Any:
        return self.request("GET", f"/tasks/{provider_task_id}/result")

    def upload_asset(self, payload: dict[str, Any]) -> Any:
        return self.request("POST", "/assets", json=payload)

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
