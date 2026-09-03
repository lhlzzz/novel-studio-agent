"""HTTP owner for Lechuang. Endpoints are not guessed; live traffic stays blocked."""

from __future__ import annotations

import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from creative.errors import AuthError, ProviderBlocked, RateLimited
from creative.providers.lechuang.capabilities import load_models
from creative.providers.lechuang.schemas import LechuangAuth

CONTRACT_VERIFIED = False
MAX_POLL_COUNT = 30
MAX_WAIT_SECONDS = 180
BACKOFF_SECONDS = (1, 2, 4, 8, 15)


def _lechuang_secret() -> tuple[str, str]:
    root = os.getenv("MEITI_SECRET_DIR", "").strip()
    if not root:
        return "", ""
    from pathlib import Path
    from social.auth.secrets import RuntimeSecretStore, SecretStoreError, secret_id
    path = Path(root)
    if not path.is_dir():
        return "", ""
    try:
        store = RuntimeSecretStore(path, production=True)
        payload = store.get_json(secret_id("lechuang", "api")) or {}
    except SecretStoreError:
        return "", ""
    return str(payload.get("api_url") or "").strip(), str(payload.get("api_key") or "").strip()


class LechuangClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        models = load_models()
        contract = models.get("contract") or {}
        self.contract_verified = bool(contract.get("verified")) and CONTRACT_VERIFIED
        self.contract_reason = str(contract.get("reason") or "Lechuang API contract unverified")
        stored_url, stored_key = _lechuang_secret()
        env_url = os.getenv("LECHUANG_API_URL", "").strip()
        self.base_url = (base_url if base_url is not None else (stored_url or env_url)).rstrip("/")
        if api_key is not None:
            key = api_key
        else:
            key = stored_key or os.getenv("LECHUANG_API_KEY", "")
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
        if not path:
            raise ProviderBlocked("lechuang", "Lechuang endpoint missing from verified contract")
        return self._http(method, path, **kwargs)

    def map_http_error(self, status_code: int, body: str = "", headers: dict[str, str] | None = None) -> None:
        if int(status_code) in {401, 403}:
            raise AuthError("Lechuang authentication failed", provider="lechuang")
        if int(status_code) == 429:
            self.handle_rate_limit(status_code, headers)
        if int(status_code) >= 500:
            raise ProviderBlocked("lechuang", f"provider failure HTTP {status_code}", details={"retryable": True, "body": body[:300]})
        raise ProviderBlocked("lechuang", f"invalid response HTTP {status_code}", details={"body": body[:300]})

    def _endpoint(self, name: str, **fmt: Any) -> str:
        endpoints = ((load_models().get("contract") or {}).get("endpoints") or {})
        path = str(endpoints.get(name) or "").strip()
        if not path:
            raise ProviderBlocked("lechuang", f"Lechuang {name} endpoint missing from verified contract")
        return path.format(**fmt)

    def _require_ready(self) -> None:
        ready, reason = self.live_ready()
        if ready:
            return
        if "LECHUANG_API_KEY" in reason:
            raise AuthError(reason, provider="lechuang")
        raise ProviderBlocked("lechuang", reason)

    def _http(self, method: str, path: str, **kwargs: Any) -> Any:
        import json
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        payload = kwargs.get("json")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        request = Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    raise ProviderBlocked("lechuang", "missing result")
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ProviderBlocked("lechuang", "invalid response") from exc
        except HTTPError as exc:
            body = exc.read().decode("utf-8", "replace") if hasattr(exc, "read") else str(exc)
            headers = {key: value for key, value in (exc.headers.items() if exc.headers else [])}
            self.map_http_error(exc.code, body, headers)
            raise ProviderBlocked("lechuang", f"invalid response HTTP {exc.code}")
        except TimeoutError as exc:
            raise ProviderBlocked("lechuang", "HTTP timeout", details={"retryable": True}) from exc
        except URLError as exc:
            raise ProviderBlocked("lechuang", f"provider failure: {exc.reason}", details={"retryable": True}) from exc

    def create_task(self, kind: str, payload: dict[str, Any]) -> Any:
        self._require_ready()
        return self.request("POST", self._endpoint("create_task"), json={"kind": kind, "payload": payload})

    def get_task(self, provider_task_id: str) -> Any:
        self._require_ready()
        return self.request("GET", self._endpoint("get_task", task_id=provider_task_id))

    def cancel_task(self, provider_task_id: str) -> Any:
        self._require_ready()
        return self.request("POST", self._endpoint("cancel_task", task_id=provider_task_id))

    def get_result(self, provider_task_id: str) -> Any:
        self._require_ready()
        return self.request("GET", self._endpoint("get_result", task_id=provider_task_id))

    def upload_asset(self, payload: dict[str, Any]) -> Any:
        self._require_ready()
        return self.request("POST", self._endpoint("upload"), json=payload)

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
