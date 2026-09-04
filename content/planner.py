"""Episode planner and content calendar. ContinuityRuntime remains the composition root."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from content.models import ContentCalendarEntry, EpisodeConcept, IsolationError, utcnow
from content.store import ContinuityStore
from content.tasks import today_iso


ROTATION_KEYS = ("scene", "topic", "action", "composition")


class EpisodePlanner:
    def __init__(self, store: ContinuityStore) -> None:
        self.store = store

    def plan_next(
        self,
        *,
        account_id: str,
        request: str = "",
        format: str = "image",
    ) -> EpisodeConcept:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        profile = self.store.get_account_profile(account_id)
        series = self.store.get_series(account.series_id, account_id=account_id) if account.series_id else self.store.active_series(account_id)
        episodes = self.store.list_episodes(series.series_id) if series else []
        recent = episodes[-5:]
        recent_topics = tuple(item.title or item.brief for item in recent if item.title or item.brief)
        learning = self.store.list_learning(account_id=account_id, platform=account.platform)
        learning_basis = tuple(
            item.next_recommendation or item.what_worked or item.reason
            for item in learning
            if item.platform in {account.platform, "GLOBAL"} and (item.next_recommendation or item.what_worked or item.reason)
        )[:6]
        dna = self.store.get_creative_dna(account_id, account.platform)
        requested = (request or "").strip()
        topic = requested or _rotate_topic(recent_topics, profile=profile, dna=dna)
        if _too_similar(topic, recent_topics) and not _serial_allowed(series):
            topic = _differentiate(topic, recent_topics)
        title = topic[:40] or "今日内容"
        refs = []
        if recent and recent[-1].primary_asset_id:
            refs.append(recent[-1].primary_asset_id)
        reason_parts = [
            f"platform={account.platform}",
            f"series={series.name if series else 'none'}",
        ]
        if learning_basis:
            reason_parts.append("learning=" + "; ".join(learning_basis[:2]))
        if recent_topics:
            reason_parts.append("avoid=" + ", ".join(recent_topics[-2:]))
        return EpisodeConcept(
            account_id=account_id,
            platform=account.platform,
            series_id=series.series_id if series else None,
            title=title,
            topic=topic,
            format=format,
            brief=requested or topic,
            reason="; ".join(reason_parts),
            freshness="NEW_PRIMARY_REQUIRED",
            continuity="keep character/world/series; new concept/prompt/primary",
            learning_basis=learning_basis,
            reference_asset_ids=tuple(refs),
            prompt_kind="VIDEO" if format == "video" else "IMAGE",
            recent_topics=recent_topics,
        )

    def ensure_calendar(
        self,
        *,
        account_id: str,
        date: str | None = None,
        topic: str = "",
        format: str = "image",
        episode_id: str | None = None,
        task_id: str | None = None,
        status: str = "PLANNED",
        slot: str = "default",
    ) -> ContentCalendarEntry:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        day = date or today_iso()
        existing = [item for item in self.store.list_calendar(account_id=account_id, date=day) if item.slot == slot]
        if existing:
            current = existing[0]
            return self.store.save_calendar_entry(ContentCalendarEntry(**{
                **current.__dict__,
                "topic": topic or current.topic,
                "format": format or current.format,
                "episode_id": episode_id or current.episode_id,
                "task_id": task_id or current.task_id,
                "status": status or current.status,
                "updated_at": utcnow(),
            }))
        return self.store.save_calendar_entry(ContentCalendarEntry(
            calendar_id=uuid4().hex,
            account_id=account_id,
            platform=account.platform,
            date=day,
            slot=slot,
            episode_id=episode_id,
            task_id=task_id,
            status=status,
            topic=topic,
            format=format,
        ))

    def tomorrow(self, *, account_id: str) -> dict[str, Any]:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        day = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
        rows = self.store.list_calendar(account_id=account_id, date=day)
        concept = self.plan_next(account_id=account_id)
        if not rows:
            entry = self.ensure_calendar(account_id=account_id, date=day, topic=concept.topic, format=concept.format, status="PLANNED")
            rows = [entry]
        entry = rows[0]
        learning = self.store.list_learning(account_id=account_id, platform=account.platform)
        return {
            "date": day,
            "platform": account.platform,
            "account_id": account_id,
            "topic": entry.topic or concept.topic,
            "format": entry.format or concept.format,
            "episode_id": entry.episode_id,
            "prompt_kind": concept.prompt_kind,
            "creative_task": "CREATIVE_EXECUTION",
            "expected_action": "compile prompt, operator Lechuang, import asset",
            "reference_assets": list(concept.reference_asset_ids),
            "learning_basis": list(concept.learning_basis) or [item.reason for item in learning[:3] if item.reason],
            "calendar_id": entry.calendar_id,
            "status": entry.status,
        }


def _rotate_topic(recent: tuple[str, ...], *, profile, dna) -> str:
    pillars = []
    if profile is not None:
        value = profile.content_pillars.value
        if isinstance(value, (list, tuple)):
            pillars = [str(item) for item in value if item]
        elif value:
            pillars = [str(value)]
    if not pillars and dna is not None:
        pillars = [str(dna.emotion_style or ""), str(dna.hook_style or "")]
    pillars = [item for item in pillars if item]
    for candidate in pillars:
        if not _too_similar(candidate, recent):
            return candidate
    return "今日生活日常"


def _too_similar(topic: str, recent: tuple[str, ...]) -> bool:
    needle = _normalize(topic)
    if not needle:
        return False
    return any(_normalize(item) == needle for item in recent[-2:])


def _differentiate(topic: str, recent: tuple[str, ...]) -> str:
    return f"{topic} · 新场景新构图".strip()


def _serial_allowed(series) -> bool:
    if series is None:
        return False
    rules = series.continuity_rules or {}
    return bool(rules.get("allow_serial_plot") or series.series_type == "serial_plot")


def _normalize(value: str) -> str:
    return "".join((value or "").lower().split())
