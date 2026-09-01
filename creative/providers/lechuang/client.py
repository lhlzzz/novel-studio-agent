"""HTTP owner for Lechuang. Endpoints are not guessed; live traffic stays blocked."""

from __future__ import annotations

import os
from typing import Any

from creative.errors import ProviderBlocked, UnsupportedCapability
from creative.providers.lechuang.capabilities import load_models
from creative.providers.lechuang.schemas import LechuangAuth

CONTRACT_VERIFIED = False


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
            raise ProviderBlocked("lechuang", reason)
        raise UnsupportedCapability(f"{method} {path}", provider="lechuang")
