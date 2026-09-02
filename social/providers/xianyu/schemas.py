from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class XianyuUser:
    user_id: str
    nick: str = ""


@dataclass(frozen=True)
class XianyuItem:
    item_id: str
    status: str = ""


def user_from_payload(payload: dict[str, Any]) -> XianyuUser:
    data = _unwrap(payload)
    return XianyuUser(user_id=str(data.get("user_id") or data.get("uid") or data.get("open_id") or ""), nick=str(data.get("nick") or data.get("user_nick") or ""))


def item_from_payload(payload: dict[str, Any]) -> XianyuItem:
    data = _unwrap(payload)
    return XianyuItem(item_id=str(data.get("item_id") or data.get("id") or ""), status=str(data.get("status") or data.get("item_status") or ""))


def _unwrap(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    for key in ("alibaba_idle_isv_item_query_response", "alibaba_idle_isv_item_publish_response", "alibaba_idle_isv_user_info_response", "data", "item"):
        value = payload.get(key)
        if isinstance(value, dict):
            inner = value.get("result") or value.get("data") or value
            if isinstance(inner, dict):
                return inner
    return payload


def map_status(raw: str) -> str:
    value = str(raw or "").lower()
    if value in {"0", "online", "onsale", "published", "sale"}:
        return "published"
    if value in {"1", "offline", "downshelf", "instock"}:
        return "offline"
    if value in {"2", "deleted", "delete"}:
        return "deleted"
    if value in {"3", "reviewing", "audit", "pending"}:
        return "reviewing"
    if value in {"4", "blocked", "punish"}:
        return "blocked"
    return "unknown"
