"""Typed boundary objects for the Postiz public API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PostizIntegration:
    """A verified Postiz channel integration."""

    id: str
    identifier: str
    name: str = ""
    account_id: str = ""
    provider: str = "postiz"
    region: str = "global"


@dataclass(frozen=True)
class PostizPost:
    """A post returned by Postiz."""

    id: str
    status: str = "unknown"
    external_id: str | None = None
    published_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PostizAccountConfig:
    """Meiti's local account mapping; IDs are never guessed."""

    platform: str
    integration_id: str | None
    status: str = "pending"


def unwrap_data(payload: Any) -> Any:
    """Return the API data field when Postiz wraps a response."""

    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload
