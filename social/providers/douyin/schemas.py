from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DouyinUser:
    open_id: str
    union_id: str = ""
    nickname: str = ""
    avatar: str = ""


@dataclass(frozen=True)
class DouyinVideo:
    item_id: str
    video_id: str = ""
    video_status: str = ""


def user_from_payload(payload: dict[str, Any]) -> DouyinUser:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    data = data or {}
    return DouyinUser(
        open_id=str(data.get("open_id") or data.get("openid") or ""),
        union_id=str(data.get("union_id") or ""),
        nickname=str(data.get("nickname") or data.get("nick_name") or ""),
        avatar=str(data.get("avatar") or data.get("avatar_url") or ""),
    )


def video_from_payload(payload: dict[str, Any]) -> DouyinVideo:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    data = data or {}
    item = data.get("item_id") or data.get("itemId") or ""
    video_id = data.get("video_id") or data.get("videoId") or ""
    status = str(data.get("video_status") or data.get("status") or data.get("item_status") or "")
    return DouyinVideo(item_id=str(item), video_id=str(video_id), video_status=status)


def map_status(raw: str) -> str:
    value = str(raw or "").lower()
    if value in {"5", "published", "public", "online", "success", "available"}:
        return "published"
    if value in {"1", "2", "4", "processing", "reviewing", "audit", "in_review", "pending"}:
        return "processing"
    if value in {"3", "6", "failed", "fail", "reject", "rejected"}:
        return "failed"
    if value in {"deleted", "7"}:
        return "deleted"
    return "unknown"
