"""Resolve natural-language account / series / continue requests without internal IDs."""

from __future__ import annotations

import re
from typing import Any

from content.models import ACCOUNT_PLATFORMS, AmbiguousTarget, IsolationError, ResolvedTarget
from content.store import ContinuityStore


PLATFORM_ALIASES = {
    "小红书": "xiaohongshu",
    "xhs": "xiaohongshu",
    "xiaohongshu": "xiaohongshu",
    "抖音": "douyin",
    "douyin": "douyin",
    "快手": "kuaishou",
    "kuaishou": "kuaishou",
    "视频号": "weixin_video",
    "微信视频号": "weixin_video",
    "weixin": "weixin_video",
    "weixin_video": "weixin_video",
    "闲鱼": "xianyu",
    "xianyu": "xianyu",
}


class IntentResolver:
    def __init__(self, store: ContinuityStore | None = None) -> None:
        self.store = store or ContinuityStore()

    def resolve(self, text: str, *, platform: str | None = None, account_id: str | None = None) -> ResolvedTarget:
        request = (text or "").strip()
        intent = classify_intent(request)
        detected_platforms = _detect_platforms(request)
        if platform:
            detected_platforms = [platform] + [item for item in detected_platforms if item != platform]
        if account_id:
            account = self.store.get_account(account_id)
            if account is None:
                raise IsolationError(f"unknown platform account: {account_id}", code="ACCOUNT_NOT_FOUND")
            if account.status != "ACTIVE":
                raise IsolationError("NO_VALID_CURRENT_ACCOUNT", code="NO_VALID_CURRENT_ACCOUNT")
            reason = "explicit_account"
        else:
            account, reason = self._resolve_account(request, detected_platforms)
        series = None
        if account:
            series_name = _detect_series_name(request)
            series_list = self.store.list_series(account.account_id)
            if series_name:
                matches = [item for item in series_list if series_name in item.name]
                if len(matches) > 1:
                    raise AmbiguousTarget("multiple series match; name the series uniquely")
                series = matches[0] if matches else None
            if series is None:
                active = [item for item in series_list if item.status == "ACTIVE"]
                if len(active) == 1:
                    series = active[0]
                elif len(active) > 1 and intent in GENERATE_INTENTS:
                    raise AmbiguousTarget("multiple active series; name the series")
                elif len(active) == 0 and len(series_list) == 1:
                    series = series_list[0]
        episode = self.store.latest_episode(series.series_id) if series else None
        extras: dict[str, Any] = {
            "continue": _is_continue(request),
            "video": _wants_video(request),
            "image": _wants_image(request),
            "platforms": detected_platforms or ([account.platform] if account else []),
            "remix": _is_remix(request),
            "intent": intent,
            "reuse_episode": intent in READ_INTENTS,
        }
        return ResolvedTarget(
            platform=account.platform,
            account_id=account.account_id,
            reason=reason,
            character_id=account.character_id,
            world_id=account.world_id,
            series_id=series.series_id if series else None,
            episode_id=episode.episode_id if episode else None,
            request=request,
            extras=extras,
        )

    def _resolve_account(self, request: str, detected_platforms: list[str]):
        named = _detect_account_name(request)
        if detected_platforms:
            candidates = self.store.list_accounts(platform=detected_platforms[0])
            if named:
                matches = [item for item in candidates if _name_match(item.display_name, named) or _name_match(item.account_id, named)]
                if len(matches) > 1:
                    raise AmbiguousTarget("multiple accounts match the named account")
                if matches:
                    if matches[0].status != "ACTIVE":
                        raise IsolationError("NO_VALID_CURRENT_ACCOUNT", code="NO_VALID_CURRENT_ACCOUNT")
                    return matches[0], "named_account"
            selected = self.store.current_account(platform=detected_platforms[0])
            if selected is not None:
                if selected.status != "ACTIVE":
                    raise IsolationError("NO_VALID_CURRENT_ACCOUNT", code="NO_VALID_CURRENT_ACCOUNT")
                return selected, "current_selection"
            active = [item for item in candidates if item.status == "ACTIVE"]
            if len(active) == 1:
                return active[0], "active_account"
            if len(active) > 1:
                raise AmbiguousTarget("multiple ACTIVE accounts on this platform; select a current account")
            raise IsolationError("NO_VALID_CURRENT_ACCOUNT", code="NO_VALID_CURRENT_ACCOUNT")
        if named:
            matches = [item for item in self.store.list_accounts() if _name_match(item.display_name, named) or _name_match(item.account_id, named)]
            if len(matches) > 1:
                raise AmbiguousTarget("multiple accounts match the named account")
            if matches:
                if matches[0].status != "ACTIVE":
                    raise IsolationError("NO_VALID_CURRENT_ACCOUNT", code="NO_VALID_CURRENT_ACCOUNT")
                return matches[0], "named_account"
        selected = self.store.current_account()
        if selected is not None:
            if selected.status != "ACTIVE":
                raise IsolationError("NO_VALID_CURRENT_ACCOUNT", code="NO_VALID_CURRENT_ACCOUNT")
            return selected, "current_selection"
        active = [item for item in self.store.list_accounts() if item.status == "ACTIVE"]
        if len(active) == 1:
            return active[0], "active_account"
        if len(active) > 1:
            raise AmbiguousTarget("multiple ACTIVE accounts; select a current account")
        raise IsolationError("NO_VALID_CURRENT_ACCOUNT", code="NO_VALID_CURRENT_ACCOUNT")

    def resolve_many(self, text: str) -> list[ResolvedTarget]:
        platforms = _detect_platforms(text) or []
        if len(platforms) <= 1:
            return [self.resolve(text)]
        return [self.resolve(text, platform=platform) for platform in platforms]


def _detect_platforms(text: str) -> list[str]:
    found: list[str] = []
    lowered = text.lower()
    for alias, platform in PLATFORM_ALIASES.items():
        if alias.lower() in lowered or alias in text:
            if platform not in found and platform in ACCOUNT_PLATFORMS:
                found.append(platform)
    excluded = _excluded_platforms(text)
    return [item for item in found if item not in excluded]


def _excluded_platforms(text: str) -> set[str]:
    excluded: set[str] = set()
    for match in re.finditer(r"不要和(.{1,12}?)一样", text):
        excluded.update(_detect_platforms_raw(match.group(1)))
    for match in re.finditer(r"不要与(.{1,12}?)一样", text):
        excluded.update(_detect_platforms_raw(match.group(1)))
    return excluded


def _detect_platforms_raw(text: str) -> list[str]:
    found: list[str] = []
    lowered = text.lower()
    for alias, platform in PLATFORM_ALIASES.items():
        if alias.lower() in lowered or alias in text:
            if platform not in found and platform in ACCOUNT_PLATFORMS:
                found.append(platform)
    return found


def _detect_account_name(text: str) -> str:
    match = re.search(r"(?:账号|account)\s*([A-Za-z0-9_\u4e00-\u9fff]+)", text)
    if match:
        return match.group(1)
    match = re.search(r"给(.{1,12}?)做", text)
    if match and "账号" in match.group(1):
        return match.group(1).replace("账号", "")
    return ""


def _detect_series_name(text: str) -> str:
    match = re.search(r"(?:系列|栏目)\s*([^\s，。]+)", text)
    return match.group(1) if match else ""


def _name_match(value: str, needle: str) -> bool:
    if not value or not needle:
        return False
    return needle.lower() in value.lower() or value.lower() in needle.lower()


def _is_continue(text: str) -> bool:
    return any(token in text for token in ("继续", "昨天", "第二天", "下一期", "接着", "continue"))


def _wants_video(text: str) -> bool:
    return any(token in text.lower() for token in ("视频", "video", "image-to-video", "做成视频"))


def _wants_image(text: str) -> bool:
    return any(token in text.lower() for token in ("图", "image", "图片")) and not _wants_video(text)


def _is_remix(text: str) -> bool:
    return any(token in text for token in ("也做一版", "版本", "不要和", "差异", "另一版"))


READ_INTENTS = ("READ", "INSPECT", "HISTORY", "SEARCH", "ANALYTICS", "DOCTOR")
GENERATE_INTENTS = ("GENERATE", "CONTINUE", "REMIX")


def classify_intent(text: str) -> str:
    lowered = (text or "").lower()
    if any(token in lowered for token in ("doctor", "健康检查", "诊断")):
        return "DOCTOR"
    if any(token in lowered for token in ("analytics", "数据", "表现", "反馈")):
        return "ANALYTICS"
    if any(token in lowered for token in ("search", "检索", "查找")):
        return "SEARCH"
    if any(token in lowered for token in ("history", "历史", "记录")):
        return "HISTORY"
    if any(token in lowered for token in ("inspect", "查看", "看一下", "inspect")):
        return "INSPECT"
    if any(token in lowered for token in ("read", "读取")):
        return "READ"
    if _is_remix(text):
        return "REMIX"
    if _is_continue(text):
        return "CONTINUE"
    return "GENERATE"
