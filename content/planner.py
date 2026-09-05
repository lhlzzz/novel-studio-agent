"""Episode planner and content calendar. ContinuityRuntime remains the composition root."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from content.models import (
    CalendarSlotConflict,
    ConfigurationBlocked,
    ContentCalendarEntry,
    ContentDecision,
    ContentNovelty,
    ContentPortfolio,
    ContentPortfolioItem,
    ContentSaturation,
    CreatorState,
    CreatorStrategy,
    EpisodeConcept,
    IsolationError,
    KnowledgeField,
    PlatformAccount,
    PlatformConnection,
    ProductionMemory,
    StrategyRevision,
    utcnow,
)
from content.store import ContinuityStore
from content.tasks import today_iso


ROTATION_KEYS = ("scene", "topic", "action", "composition")
DEFAULT_PILLARS = ("日常记录", "人物状态", "生活场景", "关系互动", "Experiment")
DEFAULT_MIX = {
    "日常记录": 0.30,
    "人物状态": 0.25,
    "生活场景": 0.20,
    "关系互动": 0.15,
    "Experiment": 0.10,
}
SCENE_VARIANTS = (
    "清晨出门",
    "通勤路上",
    "工作间隙",
    "晚饭后散步",
    "夜间回家",
    "周末市集",
    "雨天窗边",
    "厨房收尾",
    "街角停一下",
    "回家换鞋",
)
ANGLE_VARIANTS = ("真实生活切片", "过程记录", "情绪余温", "关系互动", "环境细节", "身体状态", "事后余温")
EMOTION_VARIANTS = ("松弛", "认真", "疲惫后的平静", "轻微期待", "克制喜悦")
HOOK_VARIANTS = (
    "先给结果",
    "先给现场",
    "先给身体感受",
    "先给一句心里话",
    "先给一个细节",
    "先给时间点",
    "先给未说完的一句",
)
FORMAT_VARIANTS = ("image", "video")
CONTINUE_REQUESTS = ("继续昨天", "继续", "continue yesterday", "continue", "今天做什么", "today", "做什么")


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
            if item.evidence_status == "VERIFIED"
            and item.platform in {account.platform, "GLOBAL"}
            and (item.next_recommendation or item.what_worked or item.reason)
        )[:6]
        dna = self.store.get_creative_dna(account_id, account.platform)
        decision = CreatorBrain(self.store).decide(
            account_id=account_id,
            request=request,
            format=format,
            persist=False,
        )
        topic = decision.selected_topic
        title = topic[:40] or "今日内容"
        refs = []
        if recent and recent[-1].primary_asset_id:
            refs.append(recent[-1].primary_asset_id)
        return EpisodeConcept(
            account_id=account_id,
            platform=account.platform,
            series_id=series.series_id if series else None,
            title=title,
            topic=topic,
            format=decision.selected_format or format,
            brief=decision.selected_scene or topic,
            reason=decision.reasoning,
            freshness="NEW_PRIMARY_REQUIRED",
            continuity="keep character/world/series; new concept/prompt/primary",
            learning_basis=learning_basis,
            reference_asset_ids=tuple(refs),
            prompt_kind="VIDEO" if (decision.selected_format or format) == "video" else "IMAGE",
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
            if current.episode_id and episode_id and current.episode_id != episode_id:
                raise CalendarSlotConflict(
                    f"CALENDAR_SLOT_CONFLICT account={account_id} date={day} slot={slot}"
                )
            if current.episode_id and not episode_id:
                raise CalendarSlotConflict(
                    f"CALENDAR_SLOT_CONFLICT account={account_id} date={day} slot={slot}"
                )
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
        learning = [
            item for item in self.store.list_learning(account_id=account_id, platform=account.platform)
            if item.evidence_status == "VERIFIED"
        ]
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
            "why": "Calendar owns when only; strategy/state live on CreatorBrain.",
        }


class CreatorStrategyService:
    """Unique owner of CreatorStrategy revisions. Never silently overwrite ACTIVE."""

    def __init__(self, store: ContinuityStore) -> None:
        self.store = store

    def current(self, account_id: str) -> CreatorStrategy | None:
        return self.store.current_strategy(account_id)

    def ensure_default(self, account: PlatformAccount) -> CreatorStrategy:
        existing = self.current(account.account_id)
        if existing is not None:
            return existing
        pillars = _pillars_from_account(account)
        mix = dict(account.field_value("content_mix") or DEFAULT_MIX)
        if not isinstance(mix, dict) or not mix:
            mix = dict(DEFAULT_MIX)
        strategy = CreatorStrategy(
            strategy_id=uuid4().hex,
            creator_account_id=account.account_id,
            version=1,
            objective=_text(account.growth_objective) or account.current_objective or "持续生产可延续内容",
            positioning=_text(account.positioning) or "",
            audience=_text(account.target_audience) or "",
            content_pillars=tuple(pillars),
            pillar_weights={name: float(mix.get(name) or DEFAULT_MIX.get(name) or 0) for name in pillars},
            content_mix=mix,
            growth_goal=_text(account.growth_objective) or "",
            commercial_goal=_text(account.commercial_direction) or "",
            experimentation_policy="最多 10% 实验，不覆盖主定位",
            continuity_policy="保持人物/世界/系列；每天新主素材",
            visual_policy=_text(account.visual_identity) or _text(account.visual_language) or "",
            copy_policy=_text(account.tone) or _text(account.speaking_style) or "",
            quality_bar=_text(account.quality_bar) or "真实、可延续、不重复昨天",
            status="ACTIVE",
            reason="system default strategy from creator identity",
        )
        saved = self.store.save_strategy(strategy)
        self.store.save_strategy_revision(StrategyRevision(
            revision_id=uuid4().hex,
            strategy_id=saved.strategy_id,
            creator_account_id=account.account_id,
            version=saved.version,
            why_changed="initial strategy",
            old_strategy={},
            new_strategy=saved.snapshot(),
            changed_by="system",
            effective_from=saved.effective_from,
        ))
        return saved

    def revise(
        self,
        account_id: str,
        *,
        why_changed: str,
        changed_by: str = "operator",
        **fields: Any,
    ) -> CreatorStrategy:
        current = self.ensure_default(self.store.get_account(account_id))
        if not why_changed:
            raise ConfigurationBlocked("STRATEGY_REVISION_REQUIRES_REASON", "strategy cannot be silently overwritten")
        superseded = CreatorStrategy(**{**current.__dict__, "status": "SUPERSEDED", "effective_until": utcnow(), "updated_at": utcnow()})
        self.store.save_strategy(superseded)
        nxt = CreatorStrategy(
            **{
                **current.__dict__,
                **fields,
                "strategy_id": uuid4().hex,
                "version": int(current.version or 1) + 1,
                "status": "ACTIVE",
                "reason": why_changed,
                "supersedes_strategy_id": current.strategy_id,
                "effective_from": utcnow(),
                "effective_until": None,
                "created_at": utcnow(),
                "updated_at": utcnow(),
            }
        )
        saved = self.store.save_strategy(nxt)
        self.store.save_strategy_revision(StrategyRevision(
            revision_id=uuid4().hex,
            strategy_id=saved.strategy_id,
            creator_account_id=account_id,
            version=saved.version,
            why_changed=why_changed,
            old_strategy=current.snapshot(),
            new_strategy=saved.snapshot(),
            changed_by=changed_by,
            supersedes_strategy_id=current.strategy_id,
            effective_from=saved.effective_from,
        ))
        account = self.store.get_account(account_id)
        if account is not None:
            self.store.save_account(PlatformAccount(**{
                **account.__dict__,
                "current_strategy_id": saved.strategy_id,
                "current_strategy_version": saved.version,
                "updated_at": utcnow(),
            }))
        return saved


class ContentNoveltyService:
    """Unique novelty/saturation/portfolio owner. Novelty is not asset freshness."""

    def __init__(self, store: ContinuityStore) -> None:
        self.store = store

    def portfolio(self, account_id: str, *, platform: str = "") -> ContentPortfolio:
        items = self.store.list_portfolio_items(account_id)
        now = datetime.now(timezone.utc).date()
        last_7: dict[str, int] = {}
        last_14: dict[str, int] = {}
        last_30: dict[str, int] = {}
        mix: dict[str, int] = {}
        for item in items:
            day = _parse_day(item.date or item.created_at)
            topic = item.topic or item.scene or "unknown"
            if day is not None:
                delta = (now - day).days
                if delta <= 7:
                    last_7[topic] = last_7.get(topic, 0) + 1
                if delta <= 14:
                    last_14[topic] = last_14.get(topic, 0) + 1
                if delta <= 30:
                    last_30[topic] = last_30.get(topic, 0) + 1
            pillar = item.pillar or "unknown"
            mix[pillar] = mix.get(pillar, 0) + 1
        total = sum(mix.values()) or 1
        return ContentPortfolio(
            account_id=account_id,
            platform=platform,
            items=tuple(items),
            last_7_days=last_7,
            last_14_days=last_14,
            last_30_days=last_30,
            mix={key: round(value / total, 4) for key, value in mix.items()},
        )

    def saturation(self, account_id: str, *, topic: str, scene: str, angle: str, emotion: str, hook: str) -> ContentSaturation:
        items = self.store.list_portfolio_items(account_id)[-14:]
        topic_count = _count_similar(topic, [item.topic for item in items])
        scene_count = _count_similar(scene, [item.scene for item in items])
        angle_count = _count_similar(angle, [item.angle for item in items])
        emotion_count = _count_similar(emotion, [item.emotion for item in items])
        hook_count = _count_similar(hook, [item.hook for item in items])
        peak = max(topic_count, scene_count, angle_count, emotion_count, hook_count)
        if peak >= 4:
            action = "avoid"
        elif peak >= 3:
            action = "reduce"
        elif peak == 0:
            action = "increase"
        else:
            action = "continue"
        return ContentSaturation(
            account_id=account_id,
            topic=topic,
            scene=scene,
            angle=angle,
            emotion=emotion,
            hook=hook,
            topic_count=topic_count,
            scene_count=scene_count,
            angle_count=angle_count,
            emotion_count=emotion_count,
            hook_count=hook_count,
            action=action,
        )

    def evaluate(
        self,
        account_id: str,
        *,
        topic: str,
        scene: str,
        angle: str,
        emotion: str,
        hook: str,
        visual: str = "",
        narrative: str = "",
        format: str = "image",
        previous_topics: tuple[str, ...] = (),
        previous_scenes: tuple[str, ...] = (),
        previous_angles: tuple[str, ...] = (),
        previous_hooks: tuple[str, ...] = (),
        user_override: bool = False,
    ) -> ContentNovelty:
        sat = self.saturation(account_id, topic=topic, scene=scene, angle=angle, emotion=emotion, hook=hook)
        topic_v = _verdict(topic, previous_topics, sat.topic_count, user_override=user_override)
        scene_v = _verdict(scene, previous_scenes, sat.scene_count, user_override=user_override)
        angle_v = _verdict(angle, previous_angles, sat.angle_count, user_override=user_override)
        hook_v = _verdict(hook, previous_hooks, sat.hook_count, user_override=user_override)
        emotion_v = _verdict(emotion, (), sat.emotion_count, user_override=user_override)
        visual_v = "SATURATED" if sat.scene_count >= 3 and not user_override else ("LOW_NOVELTY" if sat.scene_count >= 2 else "NOVEL")
        narrative_v = "DUPLICATE" if _too_similar(narrative or topic, previous_topics) and not user_override else topic_v
        format_v = "LOW_NOVELTY" if format and _too_similar(format, tuple(item.format for item in self.store.list_portfolio_items(account_id)[-7:])) else "NOVEL"
        ranks = {"DUPLICATE": 3, "SATURATED": 2, "LOW_NOVELTY": 1, "NOVEL": 0}
        verdict = max(
            (topic_v, scene_v, angle_v, emotion_v, visual_v, narrative_v, format_v, hook_v),
            key=lambda item: ranks.get(item, 0),
        )
        if user_override:
            verdict = "NOVEL" if verdict == "DUPLICATE" else verdict
        reason = f"topic={topic_v} scene={scene_v} angle={angle_v} hook={hook_v} saturation={sat.action}"
        return ContentNovelty(
            account_id=account_id,
            verdict=verdict,
            topic=topic_v,
            angle=angle_v,
            scene=scene_v,
            visual=visual_v,
            emotional=emotion_v,
            narrative=narrative_v,
            format=format_v,
            hook=hook_v,
            reason=reason,
        )


class ProductionMemoryService:
    """Unique production-memory owner. ContinuityMemory remains a projection."""

    def __init__(self, store: ContinuityStore) -> None:
        self.store = store

    def latest(self, account_id: str) -> ProductionMemory | None:
        return self.store.latest_production_memory(account_id)

    def resolve_conflict(self, memories: list[ProductionMemory]) -> ProductionMemory | None:
        live = [item for item in memories if item.status in {"CURRENT", "VERIFIED"}]
        if not live:
            live = [item for item in memories if item.status not in {"SUPERSEDED", "EXPIRED"}]
        if not live:
            return None
        live.sort(key=lambda item: (item.effective_from or item.created_at or "", item.importance, item.confidence))
        return live[-1]

    def record(self, memory: ProductionMemory) -> ProductionMemory:
        if memory.status == "CURRENT":
            current = self.store.list_production_memories(memory.account_id, status="CURRENT")
            for item in current:
                if item.memory_id == memory.memory_id:
                    continue
                explicit = memory.supersedes_id == item.memory_id
                same_episode = bool(item.episode_id) and item.episode_id == memory.episode_id
                next_status = "SUPERSEDED" if explicit or same_episode or not item.episode_id else "HISTORICAL"
                self.store.save_production_memory(replace(item, status=next_status, updated_at=utcnow()))
        saved = self.store.save_production_memory(memory)
        try:
            from memory.service import get_memory_service
            get_memory_service().remember(
                title=f"Production {saved.episode_id or saved.memory_id[:8]}",
                content=saved.what_was_produced or saved.next_direction,
                scope_type="EPISODE",
                account_id=saved.account_id,
                platform=saved.platform,
                series_id=saved.series_id,
                episode_id=saved.episode_id,
                character_id=saved.character_id,
                world_id=saved.world_id,
                source_type="production",
                tags=("PRODUCTION_MEMORY", saved.platform),
                document_id=f"production-memory-{saved.memory_id}",
            )
        except Exception:
            pass
        return saved


class CreatorBrain:
    """Creator Brain: strategy + state + portfolio + novelty + decision. One owner."""

    def __init__(self, store: ContinuityStore) -> None:
        self.store = store
        self.strategy = CreatorStrategyService(store)
        self.novelty = ContentNoveltyService(store)
        self.memory = ProductionMemoryService(store)

    def ensure_identity(self, account: PlatformAccount) -> tuple[CreatorStrategy, CreatorState, PlatformConnection]:
        strategy = self.strategy.ensure_default(account)
        connection = self.store.get_platform_connection(account.account_id, account.platform)
        if connection is None:
            connected = bool(account.social_account_id or account.credential_ref)
            connection = self.store.save_platform_connection(PlatformConnection(
                connection_id=f"conn-{account.account_id}",
                creator_account_id=account.account_id,
                platform=account.platform,
                provider=account.platform,
                external_account_id=account.external_account_id,
                connection_status="CONNECTED" if connected else "NOT_CONNECTED",
                credential_ref=account.credential_ref,
                social_account_id=account.social_account_id,
            ))
        state = self.store.get_creator_state(account.account_id)
        if state is None:
            state = self.store.save_creator_state(CreatorState(
                state_id=uuid4().hex,
                creator_account_id=account.account_id,
                current_phase=account.current_phase or "DAY_1",
                current_objective=account.current_objective or strategy.objective,
                current_focus=_text(account.content_direction) or "",
                current_series=account.series_id,
                current_episode=account.current_episode_id,
                current_content_mix=dict(strategy.content_mix),
                current_strategy_id=strategy.strategy_id,
                current_strategy_version=strategy.version,
                next_recommended_direction="开始第一条内容",
            ))
        if account.current_strategy_id != strategy.strategy_id:
            self.store.save_account(PlatformAccount(**{
                **account.__dict__,
                "current_strategy_id": strategy.strategy_id,
                "current_strategy_version": strategy.version,
                "updated_at": utcnow(),
            }))
        return strategy, state, connection

    def decide(
        self,
        *,
        account_id: str,
        request: str = "",
        format: str = "image",
        persist: bool = True,
        user_override: bool = False,
    ) -> ContentDecision:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        strategy, state, _connection = self.ensure_identity(account)
        series = self.store.get_series(account.series_id, account_id=account_id) if account.series_id else self.store.active_series(account_id)
        previous = self.store.latest_episode(series.series_id) if series else None
        portfolio = self.novelty.portfolio(account_id, platform=account.platform)
        memory = self.memory.latest(account_id)
        requested = _content_request(request)
        idea_decision = "ACCEPT"
        modification = ""
        pillars = list(strategy.content_pillars) or list(DEFAULT_PILLARS)
        selected_pillar = _underused_pillar(pillars, strategy.content_mix or DEFAULT_MIX, portfolio.mix)
        selected_scene = _pick_variant(SCENE_VARIANTS, [item.scene for item in portfolio.items])
        selected_angle = _pick_variant(ANGLE_VARIANTS, [item.angle for item in portfolio.items])
        selected_emotion = _pick_variant(EMOTION_VARIANTS, [item.emotion for item in portfolio.items])
        selected_hook = _pick_variant(HOOK_VARIANTS, [item.hook for item in portfolio.items])
        selected_topic = requested or (memory.next_direction if memory and memory.next_direction else "")
        if not selected_topic:
            selected_topic = f"{selected_pillar} · {selected_scene}"
        if _too_similar(selected_topic, tuple(state.recent_topics) + tuple(portfolio.last_7_days)):
            selected_topic = f"{selected_pillar} · {selected_scene} · {selected_angle}"
        if requested:
            fit = _idea_fit(requested, account, strategy)
            if fit == "REJECT":
                idea_decision = "REJECT"
                modification = "这个想法偏离账号定位，不能作为今天的主内容。"
            elif fit == "MODIFY" or _too_similar(requested, tuple(state.recent_topics)):
                idea_decision = "MODIFY"
                selected_angle = "生活余温而不是训练记录"
                selected_scene = _pick_variant(SCENE_VARIANTS, [item.scene for item in portfolio.items] + [requested])
                modification = f"我保留你的「{requested}」方向，但将场景调整为「{selected_scene} / {selected_angle}」。"
                selected_topic = f"{requested} · {selected_angle}"
        novelty = self.novelty.evaluate(
            account_id,
            topic=selected_topic,
            scene=selected_scene,
            angle=selected_angle,
            emotion=selected_emotion,
            hook=selected_hook,
            visual=selected_scene,
            narrative=selected_topic,
            format=format,
            previous_topics=tuple(state.recent_topics) + tuple(item.title or item.brief for item in ([previous] if previous else [])),
            previous_scenes=tuple(item.scene for item in portfolio.items[-7:]),
            previous_angles=tuple(item.angle for item in portfolio.items[-7:]),
            previous_hooks=tuple(item.hook for item in portfolio.items[-7:]),
            user_override=user_override or idea_decision == "ACCEPT" and bool(requested) and not _too_similar(requested, tuple(state.recent_topics)),
        )
        if novelty.verdict in {"DUPLICATE", "SATURATED"} and idea_decision != "REJECT" and not user_override:
            idea_decision = "MODIFY" if requested else "ACCEPT"
            selected_scene = _pick_variant(SCENE_VARIANTS, [item.scene for item in portfolio.items] + [selected_scene])
            selected_angle = _pick_variant(ANGLE_VARIANTS, [item.angle for item in portfolio.items] + [selected_angle])
            selected_topic = _differentiate(selected_topic, tuple(state.recent_topics))
            modification = modification or f"最近该主题已{novelty.topic}，改为 {selected_topic}。"
            novelty = self.novelty.evaluate(
                account_id,
                topic=selected_topic,
                scene=selected_scene,
                angle=selected_angle,
                emotion=selected_emotion,
                hook=selected_hook,
                format=format,
                previous_topics=tuple(state.recent_topics),
                previous_scenes=tuple(item.scene for item in portfolio.items[-7:]),
                previous_angles=tuple(item.angle for item in portfolio.items[-7:]),
                previous_hooks=tuple(item.hook for item in portfolio.items[-7:]),
                user_override=user_override,
            )
        if novelty.verdict == "DUPLICATE" and not user_override and not _serial_allowed(series):
            raise ConfigurationBlocked("TOPIC_ROTATION", "consecutive identical topic/scene/action is blocked unless series allows continuation")
        saturation = self.novelty.saturation(account_id, topic=selected_topic, scene=selected_scene, angle=selected_angle, emotion=selected_emotion, hook=selected_hook)
        avoids = tuple(dict.fromkeys([item for item in list(state.saturated_topics) + list(state.recent_topics[-3:]) if item]))
        reasoning_parts = [
            f"account={account.label()}",
            f"platform={account.platform}",
            f"strategy=v{strategy.version} {strategy.objective or strategy.positioning or 'unspecified'}",
            f"phase={state.current_phase or 'unset'}",
            f"pillar={selected_pillar}",
            f"mix={portfolio.mix or strategy.content_mix}",
            f"novelty={novelty.verdict}",
            f"saturation={saturation.action}",
        ]
        if memory:
            reasoning_parts.append(f"memory={memory.next_direction or memory.what_should_continue or memory.what_was_produced}")
        if modification:
            reasoning_parts.append(modification)
        if previous:
            reasoning_parts.append(f"continue after {previous.title or previous.episode_id}")
        unknown = [name for name in ("positioning", "target_audience", "account_subject") if not account.known(name)]
        if unknown:
            reasoning_parts.append("unknown=" + ",".join(unknown))
        decision = ContentDecision(
            decision_id=uuid4().hex,
            account_id=account_id,
            platform=account.platform,
            strategy_id=strategy.strategy_id,
            creator_state_id=state.state_id,
            previous_episode_id=previous.episode_id if previous else None,
            selected_pillar=selected_pillar,
            selected_topic=selected_topic,
            selected_angle=selected_angle,
            selected_format=format,
            selected_scene=selected_scene,
            selected_emotion=selected_emotion,
            selected_hook=selected_hook,
            idea_decision=idea_decision,
            reasoning="; ".join(reasoning_parts),
            constraints=("NEW_PRIMARY_REQUIRED", "character/world lock", "no OAuth required"),
            avoids=avoids,
            expected_effect="推进系列并避免主题坍缩",
            confidence=0.72 if novelty.verdict == "NOVEL" else 0.45,
            user_request=request,
        )
        if persist and idea_decision != "REJECT":
            self.store.save_content_decision(decision)
        return decision


def _pillars_from_account(account: PlatformAccount) -> list[str]:
    value = account.field_value("content_pillars")
    if isinstance(value, (list, tuple)):
        rows = [str(item) for item in value if item]
        if rows:
            if "Experiment" not in rows and "experiment" not in {item.lower() for item in rows}:
                rows.append("Experiment")
            return rows
    if value:
        return [str(value), "Experiment"]
    return list(DEFAULT_PILLARS)


def _text(field: Any) -> str:
    if isinstance(field, KnowledgeField):
        return "" if not field.known() else str(field.value or "")
    return str(field or "")


def _parse_day(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _count_similar(needle: str, haystack: list[str]) -> int:
    return sum(1 for item in haystack if _too_similar(needle, (item,)))


def _verdict(value: str, recent: tuple[str, ...], count: int, *, user_override: bool) -> str:
    if user_override:
        return "NOVEL"
    if _too_similar(value, recent[-1:]):
        return "DUPLICATE"
    if count >= 4 or _too_similar(value, recent[-7:]) and count >= 3:
        return "SATURATED"
    if count >= 2 or _too_similar(value, recent[-3:]):
        return "LOW_NOVELTY"
    return "NOVEL"


def _pick_variant(options: tuple[str, ...], used: list[str]) -> str:
    for item in options:
        if not _too_similar(item, tuple(used[-7:])):
            return item
    return options[len(used) % len(options)]


def _underused_pillar(pillars: list[str], target: dict[str, float], actual: dict[str, float]) -> str:
    best = pillars[0]
    best_gap = -999
    for name in pillars:
        gap = float(target.get(name) or 0) - float(actual.get(name) or 0)
        if gap > best_gap:
            best = name
            best_gap = gap
    return best


def _idea_fit(request: str, account: PlatformAccount, strategy: CreatorStrategy) -> str:
    forbidden = account.field_value("forbidden_topics") or account.field_value("taboos") or ()
    if isinstance(forbidden, str):
        forbidden = (forbidden,)
    needle = _normalize(request)
    for item in forbidden:
        if item and _normalize(str(item)) in needle:
            return "REJECT"
    positioning = _normalize(strategy.positioning or _text(account.positioning))
    if positioning and needle and positioning not in needle and needle not in positioning and len(request) > 8:
        commercial = _normalize(strategy.commercial_goal or _text(account.commercial_direction))
        if commercial and commercial in needle:
            return "MODIFY"
    return "ACCEPT"


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


def _content_request(request: str) -> str:
    text = (request or "").strip()
    if not text:
        return ""
    if _normalize(text) in {_normalize(item) for item in CONTINUE_REQUESTS}:
        return ""
    return text


def _too_similar(topic: str, recent: tuple[str, ...]) -> bool:
    needle = _normalize(topic)
    if not needle:
        return False
    return any(_normalize(item) == needle for item in recent if item)


def _differentiate(topic: str, recent: tuple[str, ...]) -> str:
    return f"{topic} · 新场景新构图".strip()


def _serial_allowed(series) -> bool:
    if series is None:
        return False
    rules = series.continuity_rules or {}
    return bool(rules.get("allow_serial_plot") or series.series_type == "serial_plot")


def _normalize(value: str) -> str:
    return "".join((value or "").lower().split())
