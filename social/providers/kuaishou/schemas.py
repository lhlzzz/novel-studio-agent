from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class KuaishouUser:
    user_id: str
    name: str = ""
    avatar: str = ""


@dataclass(frozen=True)
class KuaishouPhoto:
    photo_id: str
    caption: str = ""
    pending: bool | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None


def user_from_payload(payload: dict[str, Any]) -> KuaishouUser:
    data = payload.get("user_info") or payload.get("data") or payload
    data = data if isinstance(data, dict) else {}
    return KuaishouUser(
        user_id=str(data.get("user_id") or data.get("open_id") or data.get("id") or ""),
        name=str(data.get("name") or data.get("nickname") or ""),
        avatar=str(data.get("head") or data.get("avatar") or ""),
    )


def photo_from_payload(payload: dict[str, Any]) -> KuaishouPhoto:
    video = payload.get("video_info") or payload.get("photo") or payload.get("data") or payload
    video = video if isinstance(video, dict) else {}
    pending = video.get("pending")
    return KuaishouPhoto(
        photo_id=str(video.get("photo_id") or video.get("photoId") or ""),
        caption=str(video.get("caption") or ""),
        pending=bool(pending) if pending is not None else None,
        view_count=_int(video.get("view_count")),
        like_count=_int(video.get("like_count")),
        comment_count=_int(video.get("comment_count")),
    )


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def map_status(photo: KuaishouPhoto) -> str:
    if photo.pending is True:
        return "processing"
    if photo.pending is False and photo.photo_id:
        return "published"
    if photo.photo_id:
        return "processing"
    return "unknown"
