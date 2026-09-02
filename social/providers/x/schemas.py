"""Official X API v2 objects used by the native adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class XUser:
    id: str
    username: str
    name: str = ""
    profile_image_url: str = ""


@dataclass(frozen=True)
class XTweet:
    id: str
    text: str = ""
    created_at: str | None = None
    public_metrics: dict[str, Any] | None = None


def user_from_payload(payload: dict[str, Any]) -> XUser:
    data = payload.get("data") if "data" in payload else payload
    data = data or {}
    return XUser(
        id=str(data.get("id") or ""),
        username=str(data.get("username") or ""),
        name=str(data.get("name") or ""),
        profile_image_url=str(data.get("profile_image_url") or ""),
    )


def tweet_from_payload(payload: dict[str, Any]) -> XTweet:
    data = payload.get("data") if "data" in payload else payload
    data = data or {}
    return XTweet(
        id=str(data.get("id") or ""),
        text=str(data.get("text") or ""),
        created_at=data.get("created_at"),
        public_metrics=data.get("public_metrics") if isinstance(data.get("public_metrics"), dict) else None,
    )
