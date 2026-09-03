"""First-class XHS handoff. This is not a Publication and has no remote post id."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any

HANDOFF_STATES = (
    "READY_FOR_XHS",
    "OPENED",
    "SUBMITTED",
    "PUBLISHED",
    "EXPIRED",
    "CANCELLED",
)

HANDOFF_TRANSITIONS = {
    "READY_FOR_XHS": {"OPENED", "SUBMITTED", "EXPIRED", "CANCELLED"},
    "OPENED": {"SUBMITTED", "EXPIRED", "CANCELLED", "READY_FOR_XHS"},
    "SUBMITTED": {"PUBLISHED", "EXPIRED", "CANCELLED"},
    "PUBLISHED": set(),
    "EXPIRED": {"CANCELLED"},
    "CANCELLED": set(),
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class IllegalHandoffTransition(ValueError):
    """Raised when an XHS handoff cannot move to the requested status."""


@dataclass(frozen=True)
class XHSHandoff:
    handoff_id: str
    account_id: str
    content_package_id: str
    platform: str = "xiaohongshu"
    provider: str = "xiaohongshu"
    status: str = "READY_FOR_XHS"
    export_path: str = ""
    content_type: str = "image_note"
    title: str = ""
    content: str = ""
    hashtags: tuple[str, ...] = ()
    images: tuple[str, ...] = ()
    video: str | None = None
    cover: str | None = None
    created_at: str = ""
    updated_at: str = ""
    expires_at: str | None = None
    distribution_job_id: str = ""
    export_status: str = "PENDING"
    package: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in HANDOFF_STATES:
            raise ValueError(f"invalid handoff status: {self.status}")
        if self.export_status not in {"PENDING", "READY", "FAILED"}:
            raise ValueError(f"invalid export_status: {self.export_status}")
        if not self.created_at:
            object.__setattr__(self, "created_at", _utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)
        if not self.expires_at:
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            object.__setattr__(self, "expires_at", (created + timedelta(days=7)).isoformat())

    def as_export(self) -> dict[str, Any]:
        payload = dict(self.package) if self.package else {
            "handoff_id": self.handoff_id,
            "platform": self.platform,
            "content_type": self.content_type,
            "title": self.title,
            "content": self.content,
            "hashtags": list(self.hashtags),
            "images": list(self.images),
            "video": self.video,
            "cover": self.cover,
        }
        payload["handoff_id"] = self.handoff_id
        payload["platform"] = self.platform
        payload["expires_at"] = self.expires_at
        forbidden = {"access_token", "refresh_token", "client_secret", "authorization_code", "token", "cookie", "app_secret"}
        return {key: value for key, value in payload.items() if key not in forbidden}


def transition_handoff(handoff: XHSHandoff, new_status: str, **changes: Any) -> XHSHandoff:
    if new_status not in HANDOFF_STATES:
        raise ValueError(f"invalid handoff status: {new_status}")
    allowed = HANDOFF_TRANSITIONS.get(handoff.status, set())
    if new_status != handoff.status and new_status not in allowed:
        raise IllegalHandoffTransition(f"{handoff.status} -> {new_status} is not allowed")
    return replace(handoff, status=new_status, updated_at=_utcnow(), **changes)


def expire_if_needed(handoff: "XHSHandoff") -> "XHSHandoff":
    expires_at = handoff.expires_at
    if not expires_at or handoff.status in {"EXPIRED", "CANCELLED", "PUBLISHED"}:
        return handoff
    expires = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) <= expires:
        return handoff
    if "EXPIRED" in HANDOFF_TRANSITIONS.get(handoff.status, set()) or handoff.status == "EXPIRED":
        return transition_handoff(handoff, "EXPIRED") if handoff.status != "EXPIRED" else handoff
    return replace(handoff, status="EXPIRED", updated_at=_utcnow())


def is_handoff_result(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    status = str(result.get("status") or "").upper()
    if status in {"READY_FOR_XHS", "HANDOFF_REQUIRED"}:
        return True
    if result.get("kind") == "handoff":
        return True
    return bool(result.get("handoff_id")) and not result.get("provider_post_id")
