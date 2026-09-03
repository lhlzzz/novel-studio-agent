"""Unique Xiaole / Lechuang creative credential owner.

XiaoleAI and Lechuang share one API key. This module is the only loader.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.xiaoleai.team/v1"
API_KEY_ENV = "XIAOLEAI_API_KEY"
BASE_URL_ENV = "XIAOLEAI_BASE_URL"
SECRET_PROVIDER = "xiaole"
SECRET_ACCOUNT = "api"
PROVIDER = "xiaole"
SERVICE = "lechuang"


@dataclass(frozen=True)
class CreativeCredential:
    provider: str = PROVIDER
    service: str = SERVICE
    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    credential_ref: str = ""
    source: str = ""

    @property
    def present(self) -> bool:
        return bool(self.api_key.strip())

    @property
    def endpoint(self) -> str:
        return (self.base_url or DEFAULT_BASE_URL).rstrip("/")


def credential_ref() -> str:
    from social.auth.secrets import secret_id
    return secret_id(SECRET_PROVIDER, SECRET_ACCOUNT)


def _secret_payload() -> tuple[str, str, str]:
    root = os.getenv("MEITI_SECRET_DIR", "").strip()
    if not root:
        return "", "", ""
    from pathlib import Path
    from social.auth.secrets import RuntimeSecretStore, SecretStoreError

    path = Path(root)
    if not path.is_dir():
        return "", "", ""
    try:
        store = RuntimeSecretStore(path, production=True)
        payload = store.get_json(credential_ref()) or {}
    except SecretStoreError:
        return "", "", ""
    key = str(payload.get("api_key") or "").strip()
    url = str(payload.get("base_url") or payload.get("api_url") or "").strip()
    return key, url, credential_ref() if key or url else ""


def load_creative_credential(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> CreativeCredential:
    stored_key, stored_url, ref = _secret_payload()
    env_key = os.getenv(API_KEY_ENV, "").strip()
    env_url = os.getenv(BASE_URL_ENV, "").strip()
    if api_key is not None:
        key = str(api_key)
        source = "constructor"
    elif stored_key:
        key = stored_key
        source = "secret"
    else:
        key = env_key
        source = "env" if key else ""
    if base_url is not None:
        url = str(base_url).strip()
    else:
        url = stored_url or env_url or DEFAULT_BASE_URL
    url = (url or DEFAULT_BASE_URL).rstrip("/")
    return CreativeCredential(
        provider=PROVIDER,
        service=SERVICE,
        api_key=str(key or "").strip(),
        base_url=url,
        credential_ref=ref,
        source=source,
    )


def credential_status(cred: CreativeCredential | None = None) -> dict:
    cred = cred or load_creative_credential()
    if cred.present:
        return {
            "status": "PASS",
            "provider": cred.provider,
            "service": cred.service,
            "shared_credential": True,
            "endpoint": cred.endpoint,
            "source": cred.source,
            "env": API_KEY_ENV,
        }
    return {
        "status": "BLOCKED_EXTERNAL",
        "provider": cred.provider,
        "service": cred.service,
        "shared_credential": True,
        "endpoint": cred.endpoint,
        "source": cred.source,
        "env": API_KEY_ENV,
        "reason": f"{API_KEY_ENV} missing",
    }
