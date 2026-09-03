"""Durable credential records. Business tables store credential_ref only."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


@dataclass(frozen=True)
class CredentialRecord:
    provider: str
    credential_ref: str
    access_token: str
    refresh_token: str | None = None
    expires_at: str | None = None
    scope: str | None = None
    scopes: str | None = None
    token_type: str = "Bearer"
    provider_account_id: str = ""
    account_id: str = ""
    issued_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    def expired(self, *, now: datetime | None = None, skew_seconds: int = 60) -> bool:
        if not self.expires_at:
            return False
        now = now or _utcnow()
        expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now + timedelta(seconds=skew_seconds) >= expires

    def has_scope(self, name: str) -> bool:
        raw = self.scopes or self.scope or ""
        scopes = {item.strip() for item in raw.replace(",", " ").split() if item.strip()}
        return name in scopes

    def to_payload(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}

    def replace(self, **changes: Any) -> "CredentialRecord":
        changes.setdefault("updated_at", _iso(_utcnow()))
        return replace(self, **changes)

    @classmethod
    def from_payload(cls, payload: dict[str, Any], *, provider: str = "", ref: str = "") -> "CredentialRecord":
        expires_at = payload.get("expires_at")
        if not expires_at and payload.get("expires_in") is not None:
            try:
                expires_at = _iso(_utcnow() + timedelta(seconds=int(payload["expires_in"])))
            except (TypeError, ValueError):
                expires_at = None
        created_at = str(payload.get("created_at") or _iso(_utcnow()) or "")
        issued_at = str(payload.get("issued_at") or created_at)
        scope = payload.get("scopes") or payload.get("scope")
        if isinstance(scope, (list, tuple)):
            scope = " ".join(str(item) for item in scope)
        scope_text = str(scope) if scope else None
        return cls(
            provider=str(payload.get("provider") or provider),
            credential_ref=str(payload.get("credential_ref") or ref),
            access_token=str(payload.get("access_token") or payload.get("token") or ""),
            refresh_token=(str(payload["refresh_token"]) if payload.get("refresh_token") else None),
            expires_at=str(expires_at) if expires_at else None,
            scope=scope_text,
            scopes=scope_text,
            token_type=str(payload.get("token_type") or "Bearer"),
            provider_account_id=str(
                payload.get("provider_account_id")
                or payload.get("open_id")
                or payload.get("openid")
                or payload.get("user_id")
                or ""
            ),
            account_id=str(payload.get("account_id") or ""),
            issued_at=issued_at,
            created_at=created_at,
            updated_at=str(payload.get("updated_at") or created_at),
        )
