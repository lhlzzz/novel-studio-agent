"""Account-world continuity runtime. Creative generation still goes through CreativeRuntime."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4

from content.assets import PlatformAssetService, ReferenceAssetResolver
from content.compiler import PromptCompiler
from content.continuity import ContinuityEngine
from content.dna import merge_creative_dna
from content.models import (
    CREATOR_KNOWLEDGE_FIELDS,
    LIFECYCLE_OWNERS,
    AccountContext,
    AccountOperatingState,
    AccountProfile,
    AccountWorld,
    AnalyticsRecord,
    AssetLineage,
    AssetReferenceSnapshot,
    CharacterRevision,
    ConfigurationBlocked,
    ContentDecision,
    ContentNovelty,
    ContentPackage,
    ContentPortfolioItem,
    ContentSeries,
    ContinuityMemory,
    CreatorState,
    CreatorTask,
    Episode,
    IsolationError,
    KnowledgeField,
    LearningRecord,
    LifecycleTransition,
    ManualOverride,
    MemoryWritebackError,
    PatternPromotion,
    PerformanceFeedback,
    PlatformAccount,
    PlatformLearningProfile,
    ProductionEvidence,
    ProductionMemory,
    ProductionRun,
    PromptPackage,
    PromptPattern,
    ResolvedTarget,
    VirtualCharacter,
    WorldRevision,
    knowledge_field,
    utcnow,
)

PROFILE_KNOWLEDGE_FIELDS = (
    "account_objective",
    "target_audience",
    "positioning",
    "content_pillars",
    "brand_voice",
    "visual_style",
    "content_frequency",
    "preferred_publish_windows",
    "content_formats",
    "operating_rules",
    "forbidden_rules",
    "manual_notes",
)
from content.planner import CreatorBrain, CreatorStrategyService, EpisodePlanner
from content.platform_policy import differentiate_package, platform_policy
from content.qa import CharacterContinuityQA, CrossAccountIsolationGuard
from content.readiness import ProductionReadinessService
from content.resolve import IntentResolver
from content.store import ContinuityStore
from content.tasks import TaskOS, due_iso, sync_operating_state, today_iso


@dataclass
class ContinuityRuntime:
    store: ContinuityStore
    engine: ContinuityEngine
    resolver: IntentResolver
    isolation: CrossAccountIsolationGuard
    character_qa: CharacterContinuityQA

    @classmethod
    def create(cls, *, store: ContinuityStore | None = None, production: bool = False) -> "ContinuityRuntime":
        if store is None:
            store = ContinuityStore.production() if production else ContinuityStore()
        engine = ContinuityEngine(store)
        return cls(
            store=store,
            engine=engine,
            resolver=IntentResolver(store),
            isolation=CrossAccountIsolationGuard(store),
            character_qa=CharacterContinuityQA(),
        )

    @classmethod
    def testing(cls) -> "ContinuityRuntime":
        return cls.create(store=ContinuityStore.testing(), production=False)

    @classmethod
    def production(cls) -> "ContinuityRuntime":
        return cls.create(production=True)

    def create_account(self, *, platform: str, display_name: str, account_id: str | None = None, external_account_id: str = "", credential_ref: str = "", social_account_id: str | None = None) -> PlatformAccount:
        account = PlatformAccount(
            account_id=account_id or uuid4().hex,
            platform=platform,
            display_name=display_name,
            external_account_id=external_account_id or display_name,
            credential_ref=credential_ref,
            social_account_id=social_account_id,
            status="ACTIVE" if not self.store.active_account(platform=platform) else "DRAFT",
        )
        saved = self.store.save_account(account)
        if saved.status == "ACTIVE":
            saved = self.store.select_current_account(saved.account_id, reason="create")
        self.store.save_creative_dna(merge_creative_dna(saved.account_id, saved.platform, None))
        self.store.save_learning_profile(PlatformLearningProfile(
            profile_id=f"learn-{saved.account_id}",
            account_id=saved.account_id,
            platform=saved.platform,
        ))
        PlatformAssetService(self.store).ensure_pool(account_id=saved.account_id, platform=saved.platform)
        self.store.save_memory(ContinuityMemory(
            memory_id=uuid4().hex,
            kind="account",
            account_id=saved.account_id,
            subject_id=saved.account_id,
            key="created",
            value={"platform": saved.platform, "display_name": saved.display_name},
        ))
        self.store.save_account_profile(AccountProfile(
            account_id=saved.account_id,
            platform=saved.platform,
            display_name=saved.display_name,
            external_account_id=saved.external_account_id,
            status=saved.status,
            character_id=saved.character_id,
            world_id=saved.world_id,
            series_id=saved.series_id,
        ))
        self.store.save_operating_state(AccountOperatingState(
            account_id=saved.account_id,
            platform=saved.platform,
            current_objective="",
            next_action="ACCOUNT_SETUP",
        ))
        CreatorBrain(self.store).ensure_identity(saved)
        return self.store.get_account(saved.account_id) or saved

    def bind_character(self, account_id: str, character: VirtualCharacter) -> VirtualCharacter:
        self.isolation.assert_owned(account_id=account_id)
        if character.account_id != account_id:
            raise IsolationError("character account_id must match the platform account")
        saved = self.store.save_character(character)
        account = self.store.get_account(account_id)
        self.store.save_account(PlatformAccount(**{**account.__dict__, "character_id": saved.character_id, "updated_at": utcnow()}))
        self._sync_profile(account.account_id, character_id=saved.character_id)
        pool = self.store.get_pool(account_id=account_id, platform=account.platform)
        if pool is not None:
            self.store.save_pool(replace(pool, character_id=saved.character_id))
        self.store.save_memory(ContinuityMemory(
            memory_id=uuid4().hex,
            kind="character",
            account_id=account_id,
            subject_id=saved.character_id,
            key="identity",
            value={"name": saved.name, "version": saved.version},
        ))
        self.store.save_character_revision(CharacterRevision(
            revision_id=uuid4().hex,
            character_id=saved.character_id,
            account_id=account_id,
            version=saved.version,
            snapshot={"name": saved.name, "appearance": dict(saved.appearance_profile), "character_dna": dict(saved.character_dna)},
        ))
        return saved

    def bind_world(self, account_id: str, world: AccountWorld) -> AccountWorld:
        self.isolation.assert_owned(account_id=account_id)
        if world.account_id != account_id:
            raise IsolationError("world account_id must match the platform account")
        saved = self.store.save_world(world)
        account = self.store.get_account(account_id)
        self.store.save_account(PlatformAccount(**{**account.__dict__, "world_id": saved.world_id, "updated_at": utcnow()}))
        self._sync_profile(account.account_id, world_id=saved.world_id)
        pool = self.store.get_pool(account_id=account_id, platform=account.platform)
        if pool is not None:
            self.store.save_pool(replace(pool, world_id=saved.world_id))
        self.store.save_memory(ContinuityMemory(
            memory_id=uuid4().hex,
            kind="world",
            account_id=account_id,
            subject_id=saved.world_id,
            key="world",
            value={"name": saved.name, "theme": saved.core_theme},
        ))
        self.store.save_world_revision(WorldRevision(
            revision_id=uuid4().hex,
            world_id=saved.world_id,
            account_id=account_id,
            version=saved.version,
            snapshot={"name": saved.name, "city": saved.city, "world_dna": dict(saved.world_dna)},
        ))
        return saved

    def create_series(self, *, account_id: str, name: str, description: str = "", series_id: str | None = None) -> ContentSeries:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        series = ContentSeries(
            series_id=series_id or uuid4().hex,
            account_id=account_id,
            world_id=account.world_id,
            name=name,
            description=description,
            status="ACTIVE",
            series_goal=f"推进 {name}",
            series_theme=description or name,
            series_arc="日常连续记录",
            current_phase="DAY_1",
            phase_goal="建立可延续的账号内容",
            next_direction_candidates=("真实生活切片", "过程记录", "情绪余温"),
            completion_condition="",
        )
        saved = self.store.save_series(series)
        if account.series_id is None:
            self.store.save_account(PlatformAccount(**{**account.__dict__, "series_id": saved.series_id, "updated_at": utcnow()}))
            self._sync_profile(account.account_id, series_id=saved.series_id)
            sync_operating_state(self.store, account_id=account.account_id, platform=account.platform, current_series=saved.series_id)
        self.store.save_memory(ContinuityMemory(
            memory_id=uuid4().hex,
            kind="series",
            account_id=account_id,
            subject_id=saved.series_id,
            key="series",
            value={"name": saved.name},
        ))
        return saved

    def continue_yesterday(self, *, account_id: str, request: str = "继续昨天") -> dict[str, Any]:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        series = self.store.active_series(account_id)
        if series is None:
            raise ConfigurationBlocked("MISSING_SERIES", "continue yesterday requires an active series")
        previous = self.store.latest_episode(series.series_id)
        planned = self.produce_today(account_id=account_id, request=request, intent="CONTINUE")
        return {
            "previous_episode": previous,
            "episode": planned["episode"],
            "prompt": planned["prompt"],
            "decision": planned["decision"],
            "character_id": account.character_id,
            "world_id": account.world_id,
            "freshness": "NEW_PRIMARY_REQUIRED",
            "job_id": planned.get("job_id"),
            "job_status": planned.get("job_status"),
            "creative_provider": planned.get("creative_provider") or "lechuang",
            "model": planned.get("model"),
            "asset_id": planned.get("asset_id"),
        }

    def change_topic(self, *, account_id: str, request: str) -> dict[str, Any]:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        planned = self.produce_today(account_id=account_id, request=request, intent="GENERATE")
        return {
            "account_id": account_id,
            "character_id": account.character_id,
            "world_id": account.world_id,
            "episode": planned["episode"],
            "prompt": planned["prompt"],
            "decision": planned["decision"],
        }

    def produce_today(
        self,
        *,
        account_id: str,
        request: str = "",
        intent: str = "GENERATE",
        format: str = "image",
        kind: str | None = None,
        user_override: bool = False,
    ) -> dict[str, Any]:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        brain = CreatorBrain(self.store)
        strategy, state, connection = brain.ensure_identity(account)
        decision = brain.decide(
            account_id=account_id,
            request=request,
            format=format,
            persist=True,
            user_override=user_override,
        )
        portfolio = brain.novelty.portfolio(account_id, platform=account.platform)
        novelty = brain.novelty.evaluate(
            account_id,
            topic=decision.selected_topic,
            scene=decision.selected_scene,
            angle=decision.selected_angle,
            emotion=decision.selected_emotion,
            hook=decision.selected_hook,
            visual=decision.selected_scene,
            narrative=decision.selected_topic,
            format=decision.selected_format or format,
            previous_topics=tuple(state.recent_topics),
            previous_scenes=tuple(item.scene for item in portfolio.items[-7:]),
            previous_angles=tuple(item.angle for item in portfolio.items[-7:]),
            previous_hooks=tuple(item.hook for item in portfolio.items[-7:]),
            user_override=user_override,
        )
        memory = brain.memory.latest(account_id)
        payload = {
            "account": account,
            "platform": account.platform,
            "connection": connection,
            "strategy": strategy,
            "creator_state": state,
            "portfolio": portfolio,
            "novelty": novelty,
            "saturation": brain.novelty.saturation(
                account_id,
                topic=decision.selected_topic,
                scene=decision.selected_scene,
                angle=decision.selected_angle,
                emotion=decision.selected_emotion,
                hook=decision.selected_hook,
            ),
            "decision": decision,
            "memory": memory,
            "episode": None,
            "prompt": None,
            "status": decision.idea_decision,
        }
        if decision.idea_decision == "REJECT":
            return payload
        series = self.store.get_series(account.series_id, account_id=account_id) if account.series_id else self.store.active_series(account_id)
        if series is None:
            series = self.create_series(account_id=account_id, name=(decision.selected_topic or request or "untitled series")[:40])
        previous = self.store.latest_episode(series.series_id)
        title = (decision.selected_topic or request or "今日内容")[:40]
        brief = decision.selected_scene or decision.selected_topic or request
        episode = self.engine.create_next_episode(series.series_id, account_id=account_id, title=title, brief=brief)
        episode = self.store.save_episode(Episode(**{
            **episode.__dict__,
            "strategy_id": strategy.strategy_id if strategy else None,
            "strategy_version": strategy.version if strategy else None,
            "creator_state_id": state.state_id if state else None,
            "content_decision_id": decision.decision_id,
            "creator_state_snapshot": state.snapshot() if state else {},
            "novelty_snapshot": novelty.snapshot(),
            "portfolio_snapshot": portfolio.snapshot(),
            "updated_at": utcnow(),
        }))
        prompt_kind = kind or ("VIDEO" if (decision.selected_format or format) == "video" else "IMAGE")
        prompt = self.compile_prompt(
            account_id=account_id,
            platform=account.platform,
            request=request or decision.selected_topic,
            kind=prompt_kind,
            episode=episode,
            intent=intent,
            decision=decision,
            strategy=strategy,
            creator_state=state,
            novelty=novelty,
            production_memory=memory,
        )
        episode = self.store.get_episode(episode.episode_id, account_id=account_id) or episode
        self.store.save_portfolio_item(ContentPortfolioItem(
            item_id=uuid4().hex,
            account_id=account_id,
            pillar=decision.selected_pillar,
            topic=decision.selected_topic,
            format=decision.selected_format or format,
            scene=decision.selected_scene,
            emotion=decision.selected_emotion,
            angle=decision.selected_angle,
            hook=decision.selected_hook,
            series_id=series.series_id,
            episode_id=episode.episode_id,
            status=episode.content_status,
        ))
        previous_title = previous.title if previous else ""
        recorded = brain.memory.record(ProductionMemory(
            memory_id=uuid4().hex,
            account_id=account_id,
            platform=account.platform,
            status="CURRENT",
            strategy_id=strategy.strategy_id if strategy else None,
            creator_state_id=state.state_id if state else None,
            episode_id=episode.episode_id,
            decision_id=decision.decision_id,
            prompt_id=prompt.prompt_id,
            character_id=account.character_id,
            world_id=account.world_id,
            series_id=series.series_id,
            scene=decision.selected_scene,
            visual_direction=decision.selected_angle,
            copy_direction=decision.selected_hook,
            what_was_produced=decision.selected_topic,
            what_changed=f"after {previous_title}" if previous_title else "first episode",
            what_should_continue="keep character/world/series; new primary asset",
            what_should_not_repeat=", ".join(decision.avoids[:4]),
            next_direction=f"{decision.selected_pillar} · 新场景",
            confidence=decision.confidence,
            importance=0.8,
            supersedes_id=memory.memory_id if memory else None,
        ))
        recent = tuple(dict.fromkeys([*list(state.recent_topics), decision.selected_topic]))[-14:]
        saturated = tuple(dict.fromkeys([*list(state.saturated_topics), *( [decision.selected_topic] if novelty.verdict in {"SATURATED", "DUPLICATE"} else [])]))[-14:]
        live_portfolio = brain.novelty.portfolio(account_id, platform=account.platform)
        underused = tuple(name for name, share in (strategy.content_mix or {}).items() if float(live_portfolio.mix.get(name) or 0) < float(share or 0))
        phase = f"DAY_{episode.episode_no}"
        state = self.store.save_creator_state(CreatorState(**{
            **state.__dict__,
            "current_phase": phase,
            "current_objective": strategy.objective if strategy else state.current_objective,
            "current_focus": decision.selected_pillar,
            "current_series": series.series_id,
            "current_episode": episode.episode_id,
            "current_content_mix": dict(live_portfolio.mix),
            "recent_topics": recent,
            "saturated_topics": saturated,
            "underused_topics": underused,
            "current_strategy_id": strategy.strategy_id if strategy else state.current_strategy_id,
            "current_strategy_version": strategy.version if strategy else state.current_strategy_version,
            "last_production_at": utcnow(),
            "last_production_episode_id": episode.episode_id,
            "next_recommended_direction": recorded.next_direction,
            "updated_at": utcnow(),
        }))
        live_series = self.store.get_series(series.series_id, account_id=account_id) or series
        self.store.save_series(ContentSeries(**{
            **live_series.__dict__,
            "current_phase": phase,
            "phase_goal": strategy.objective if strategy else live_series.phase_goal,
            "series_goal": live_series.series_goal or f"推进 {live_series.name}",
            "series_theme": live_series.series_theme or live_series.name,
            "series_arc": live_series.series_arc or "日常连续记录",
            "next_direction_candidates": tuple(dict.fromkeys([*list(live_series.next_direction_candidates), recorded.next_direction]))[:6],
            "updated_at": utcnow(),
        }))
        self.store.save_account(PlatformAccount(**{
            **account.__dict__,
            "current_strategy_id": strategy.strategy_id if strategy else account.current_strategy_id,
            "current_strategy_version": strategy.version if strategy else account.current_strategy_version,
            "current_episode_id": episode.episode_id,
            "current_phase": phase,
            "current_objective": strategy.objective if strategy else account.current_objective,
            "current_next_action": "CREATIVE_EXECUTION",
            "updated_at": utcnow(),
        }))
        payload.update({
            "episode": episode,
            "prompt": prompt,
            "creator_state": state,
            "memory": recorded,
            "portfolio": live_portfolio,
            "status": decision.idea_decision,
        })
        if prompt is not None:
            generated = self.submit_generation(
                account_id=account_id,
                episode_id=episode.episode_id,
                prompt=prompt,
                request=request or decision.selected_topic,
            )
            payload.update(generated)
            payload["status"] = generated.get("job_status") or payload["status"]
        return payload

    def today(self, *, account_id: str, request: str = "今天做什么") -> dict[str, Any]:
        planned = self.produce_today(account_id=account_id, request=request, intent="GENERATE")
        account = planned["account"]
        strategy = planned["strategy"]
        state = planned["creator_state"]
        portfolio = planned["portfolio"]
        novelty = planned["novelty"]
        decision = planned["decision"]
        episode = planned["episode"]
        prompt = planned["prompt"]
        return {
            "ACCOUNT": account.label(),
            "PLATFORM": account.platform,
            "CONNECTION": planned["connection"].connection_status if planned.get("connection") else "NOT_CONNECTED",
            "CURRENT_STATE": state.snapshot() if state else {},
            "CURRENT_STRATEGY": strategy.snapshot() if strategy else {},
            "RECENT_CONTENT": list(state.recent_topics) if state else [],
            "CONTENT_MIX": dict(portfolio.mix) if portfolio else {},
            "SATURATION": planned["saturation"].snapshot() if planned.get("saturation") else {},
            "UNDERUSED_AREAS": list(state.underused_topics) if state else [],
            "TODAY_RECOMMENDATION": decision.selected_topic if decision else "",
            "REASON": decision.reasoning if decision else "",
            "IDEA_DECISION": decision.idea_decision if decision else "",
            "EPISODE": None if episode is None else {
                "episode_id": episode.episode_id,
                "episode_no": episode.episode_no,
                "title": episode.title,
                "content_decision_id": episode.content_decision_id,
            },
            "PROMPT": None if prompt is None else {
                "prompt_id": prompt.prompt_id,
                "kind": prompt.kind,
                "copy_ready": bool(prompt.copy_ready),
            },
            "CREATIVE_PROVIDER": planned.get("creative_provider") or "lechuang",
            "MODEL": planned.get("model") or (prompt.recommended_model if prompt else ""),
            "CREATIVE_JOB": planned.get("job_id"),
            "STATUS": planned.get("job_status") or planned.get("status"),
            "WHY": decision.reasoning if decision else "",
            "Today": decision.selected_topic if decision else "",
            "Why": decision.reasoning if decision else "",
            "Platform": account.platform,
            "Provider": planned.get("creative_provider") or "lechuang",
            "Model": planned.get("model") or (prompt.recommended_model if prompt else ""),
            "NOVELTY": novelty.snapshot() if novelty else {},
            "CORE_CONTENT_PRODUCTION": "READY" if episode is not None and prompt is not None else "NOT_CONFIGURED",
        }

    def configure_identity(self, account_id: str, *, source: str = "USER_DEFINED", reason: str = "creator identity configured", **fields: Any) -> PlatformAccount:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        payload = dict(account.__dict__)
        knowledge: dict[str, Any] = {}
        for name, value in fields.items():
            if name in CREATOR_KNOWLEDGE_FIELDS:
                knowledge[name] = knowledge_field(value, source=source, reason=reason, changed_by="operator")
            elif hasattr(account, name):
                payload[name] = value
        payload.update(knowledge)
        payload["updated_at"] = utcnow()
        saved = self.store.save_account(PlatformAccount(**payload))
        profile_fields = {}
        if "growth_objective" in knowledge:
            profile_fields["account_objective"] = knowledge["growth_objective"]
        if "target_audience" in knowledge:
            profile_fields["target_audience"] = knowledge["target_audience"]
        if "positioning" in knowledge:
            profile_fields["positioning"] = knowledge["positioning"]
        if "content_pillars" in knowledge:
            profile_fields["content_pillars"] = knowledge["content_pillars"]
        if "tone" in knowledge:
            profile_fields["brand_voice"] = knowledge["tone"]
        if "visual_identity" in knowledge:
            profile_fields["visual_style"] = knowledge["visual_identity"]
        if profile_fields:
            self._sync_profile(account_id, **profile_fields)
        else:
            self._sync_profile(account_id)
        CreatorBrain(self.store).ensure_identity(saved)
        current = CreatorStrategyService(self.store).current(account_id)
        if current is not None and (current.reason.startswith("system default") or not current.positioning):
            CreatorStrategyService(self.store).revise(
                account_id,
                why_changed=reason,
                changed_by="operator",
                objective=_text_or(saved.growth_objective, current.objective),
                positioning=_text_or(saved.positioning, current.positioning),
                audience=_text_or(saved.target_audience, current.audience),
                content_pillars=tuple(saved.field_value("content_pillars") or current.content_pillars),
                content_mix=dict(saved.field_value("content_mix") or current.content_mix),
                growth_goal=_text_or(saved.growth_objective, current.growth_goal),
                commercial_goal=_text_or(saved.commercial_direction, current.commercial_goal),
                visual_policy=_text_or(saved.visual_identity, current.visual_policy),
                copy_policy=_text_or(saved.tone, current.copy_policy),
                quality_bar=_text_or(saved.quality_bar, current.quality_bar),
            )
        return self.store.get_account(account_id) or saved

    def continue_series(self, *, account_id: str, series_id: str, brief: str = "", title: str = "") -> Episode:
        episode = self.engine.create_next_episode(series_id, account_id=account_id, brief=brief, title=title)
        account = self.store.get_account(account_id)
        if account is not None:
            sync_operating_state(
                self.store,
                account_id=account_id,
                platform=account.platform,
                current_series=series_id,
                current_episode=episode.episode_id,
                current_content_status=episode.content_status,
            )
        return episode

    def prepare(self, text: str, *, platform: str | None = None, account_id: str | None = None) -> dict[str, Any]:
        target = self.resolver.resolve(text, platform=platform, account_id=account_id)
        return self.prepare_target(target, text=text)

    def prepare_target(self, target: ResolvedTarget, *, text: str) -> dict[str, Any]:
        extras = dict(target.extras or {})
        intent = str(extras.get("intent") or "GENERATE")
        account = self.store.get_account(target.account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {target.account_id}")
        series = self.store.get_series(target.series_id, account_id=account.account_id) if target.series_id else self.store.active_series(account.account_id)
        episode = None
        read_only = extras.get("reuse_episode") or intent in {"READ", "INSPECT", "HISTORY", "SEARCH", "ANALYTICS", "DOCTOR"}
        if read_only:
            if target.episode_id:
                episode = self.store.get_episode(target.episode_id, account_id=account.account_id)
            elif series is not None:
                episode = self.store.latest_episode(series.series_id)
        else:
            if series is None:
                series = self.create_series(account_id=account.account_id, name=text[:40] or "untitled series")
            episode = self.continue_series(account_id=account.account_id, series_id=series.series_id, brief=text, title=text[:40])
        target = ResolvedTarget(
            platform=account.platform,
            account_id=account.account_id,
            reason=target.reason,
            character_id=account.character_id,
            world_id=account.world_id,
            series_id=series.series_id if series else None,
            episode_id=episode.episode_id if episode else None,
            request=text,
            extras=extras,
        )
        context = self.engine.build_creative_context(target=target, request=text, brief=episode.brief if episode else text)
        isolation = self.isolation.inspect(context)
        character_qa = self.character_qa.inspect(context, store=self.store)
        account_context = AccountContext(
            account_id=account.account_id,
            platform=account.platform,
            account_name=account.display_name,
            character_id=account.character_id,
            world_id=account.world_id,
            series_id=series.series_id if series else None,
            episode_id=episode.episode_id if episode else None,
            creative_context_id=context.context_id,
            campaign_id=context.campaign_id,
            selection_reason=target.reason,
            resolution_source=target.reason,
            intent=intent,
        )
        return {
            "target": target,
            "context": context,
            "episode": episode,
            "series": series,
            "account": account,
            "account_context": account_context,
            "isolation": isolation,
            "character_qa": character_qa,
            "policy": platform_policy(account.platform),
            "creative_dna": self.store.get_creative_dna(account.account_id, account.platform),
        }

    def compile_prompt(
        self,
        *,
        account_id: str,
        platform: str,
        request: str,
        kind: str | None = None,
        episode: Episode | None = None,
        intent: str = "GENERATE",
        source_asset_id: str | None = None,
        reference_assets: list[Any] | tuple[Any, ...] = (),
        strategy=None,
        creator_state: CreatorState | None = None,
        decision: ContentDecision | None = None,
        novelty: ContentNovelty | None = None,
        production_memory: ProductionMemory | None = None,
    ) -> PromptPackage:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        if account.platform != platform:
            raise IsolationError(f"account {account_id} is {account.platform}, not {platform}")
        series = self.store.active_series(account_id)
        episode = episode or (self.store.latest_episode(series.series_id) if series else None)
        previous = self.engine.get_previous_episode(episode) if episode and episode.previous_episode_id else None
        character = self.store.get_character(account.character_id, account_id=account_id) if account.character_id else None
        world = self.store.get_world(account.world_id, account_id=account_id) if account.world_id else None
        if character is None or world is None:
            raise ConfigurationBlocked("MISSING_CHARACTER_OR_WORLD", "production compile requires account character and world")
        if self.store.get_pool(account_id=account_id, platform=platform) is None:
            raise ConfigurationBlocked("MISSING_ASSET_POOL", "production compile requires a platform asset pool")
        refs = list(reference_assets)
        if not refs:
            refs = ReferenceAssetResolver(self.store).resolve(
                account_id=account_id,
                platform=platform,
                character_id=account.character_id,
                world_id=account.world_id,
                previous_episode=previous,
            )
        records = self.store.list_learning(account_id=account_id, platform=platform)
        verified = [item for item in records if item.evidence_status == "VERIFIED" and item.platform in {platform, "GLOBAL"}]
        learning_payload: dict[str, Any] = {}
        if verified:
            learning_payload = {
                "learning_records": [
                    {
                        "learning_id": item.learning_id,
                        "platform": item.platform,
                        "what_worked": item.what_worked,
                        "next_recommendation": item.next_recommendation,
                        "reason": item.reason,
                        "source_episode_ids": list(item.source_episode_ids),
                        "evidence_status": item.evidence_status,
                    }
                    for item in verified
                ],
                "successful_patterns": tuple(
                    item.next_recommendation or item.what_worked
                    for item in verified
                    if item.what_worked or item.next_recommendation
                ),
            }
        if decision is None and episode is not None and episode.content_decision_id:
            decision = self.store.get_content_decision(episode.content_decision_id)
        if strategy is None:
            strategy = self.store.current_strategy(account_id)
        if creator_state is None:
            creator_state = self.store.get_creator_state(account_id)
        if production_memory is None:
            production_memory = self.store.latest_production_memory(account_id)
        if novelty is None and episode is not None and episode.novelty_snapshot:
            novelty = ContentNovelty(account_id=account_id, **{
                key: episode.novelty_snapshot[key]
                for key in ("verdict", "topic", "angle", "scene", "visual", "emotional", "narrative", "format", "hook", "reason")
                if key in episode.novelty_snapshot
            })
        prompt = PromptCompiler(self.store).compile(
            account_id=account_id,
            platform=platform,
            request=request,
            kind=kind,
            character=character,
            world=world,
            series=series,
            episode=episode,
            previous=previous,
            dna=self.store.get_creative_dna(account_id, platform),
            continuity=previous.continuity_context if previous else {},
            learning=learning_payload,
            reference_assets=refs,
            source_asset_id=source_asset_id,
            intent=intent,
            strategy=strategy,
            creator_state=creator_state,
            decision=decision,
            novelty=novelty,
            production_memory=production_memory,
        )
        if episode is not None:
            self.transition_episode(episode.episode_id, account_id=account_id, to_status="PROMPT_READY")
            run = self.open_production_run(account_id=account_id, platform=platform, episode_id=episode.episode_id, request=request)
            tasks = TaskOS(self.store).create_production_chain(
                account_id=account_id,
                platform=platform,
                title=request or episode.title,
                description=request,
                episode_id=episode.episode_id,
                series_id=episode.series_id,
                due_at=today_iso(),
                production_run_id=run.run_id,
            )
            plan = next((item for item in tasks if item.task_type == "CONTENT_PLAN"), None)
            prompt_task = next((item for item in tasks if item.task_type == "PROMPT_GENERATION"), None)
            os = TaskOS(self.store)
            if plan:
                os.complete_type(account_id=account_id, episode_id=episode.episode_id, task_type="CONTENT_PLAN")
            if prompt_task:
                os.complete_type(account_id=account_id, episode_id=episode.episode_id, task_type="PROMPT_GENERATION", prompt_id=prompt.prompt_id)
                os.waiting_operator(account_id=account_id, episode_id=episode.episode_id)
            current_task = TaskOS(self.store).get_next_action(account_id=account_id, episode_id=episode.episode_id)
            live_tasks = self.store.list_tasks(account_id=account_id, episode_id=episode.episode_id)
            bound_task = (
                next((item for item in live_tasks if item.task_type == "CREATIVE_EXECUTION"), None)
                or current_task
                or (self.store.get_task(prompt_task.task_id) if prompt_task else None)
            )
            if bound_task and bound_task.episode_id and bound_task.episode_id != episode.episode_id:
                raise IsolationError("production run and task episode mismatch")
            self.store.save_production_run(ProductionRun(**{
                **run.__dict__,
                "prompt_id": prompt.prompt_id,
                "task_id": bound_task.task_id if bound_task else None,
                "strategy_id": (strategy.strategy_id if strategy else None) or (episode.strategy_id if episode else None),
                "creator_state_id": (creator_state.state_id if creator_state else None) or (episode.creator_state_id if episode else None),
                "content_decision_id": (decision.decision_id if decision else None) or (episode.content_decision_id if episode else None),
                "status": "PROMPT_READY",
                "updated_at": utcnow(),
            }))
            if bound_task is not None:
                live = self.store.get_task(bound_task.task_id) or bound_task
                self.store.save_task(CreatorTask(**{
                    **live.__dict__,
                    "prompt_id": prompt.prompt_id,
                    "production_run_id": run.run_id,
                    "updated_at": utcnow(),
                }))
            EpisodePlanner(self.store).ensure_calendar(
                account_id=account_id,
                date=today_iso(),
                topic=episode.title or request,
                episode_id=episode.episode_id,
                task_id=current_task.task_id if current_task else None,
                status="PRODUCING",
                slot=episode.episode_id,
            )
            sync_operating_state(
                self.store,
                account_id=account_id,
                platform=platform,
                current_episode=episode.episode_id,
                current_task=current_task.task_id if current_task else None,
                current_content_status="AWAITING_CREATIVE",
                next_action="CREATIVE_EXECUTION",
            )
            for asset in refs:
                asset_id = getattr(asset, "asset_id", None) or str(asset)
                self.store.save_reference_snapshot(AssetReferenceSnapshot(
                    snapshot_id=uuid4().hex,
                    prompt_id=prompt.prompt_id,
                    asset_id=str(asset_id),
                    role="SCENE_REFERENCE",
                    reason="previous episode or character continuity",
                    prompt_influence="keep character/world lock; do not reuse as primary",
                ))
            self.record_evidence(
                kind="PROMPT_READY",
                account_id=account_id,
                platform=platform,
                episode_id=episode.episode_id,
                prompt_id=prompt.prompt_id,
                production_run_id=run.run_id,
                source="operator",
                detail={"copy_ready": True, "provider": "lechuang"},
            )
        return prompt

    def submit_generation(
        self,
        *,
        account_id: str,
        episode_id: str,
        prompt: PromptPackage,
        request: str = "",
        execute: bool = True,
    ) -> dict[str, Any]:
        from creative.errors import AuthError, ProviderBlocked, RateLimited, UnsupportedCapability
        from creative.idempotency import IdempotencyKey
        from integrations.contracts.creative import map_creative_status
        from integrations.providers.resolver import resolve_creative_provider

        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        episode = self.store.get_episode(episode_id, account_id=account_id)
        if episode is None:
            raise IsolationError(f"episode {episode_id} is not owned by {account_id}")
        run = self.open_production_run(account_id=account_id, platform=account.platform, episode_id=episode_id, request=request)
        spec = {
            "kind": prompt.kind,
            "model": prompt.recommended_model,
            "image_size": prompt.recommended_size,
            "aspect_ratio": prompt.aspect_ratio or prompt.recommended_ratio,
            "duration": prompt.duration,
            "negative_prompt": prompt.negative_prompt,
            "source_asset_id": prompt.source_asset_id,
        }
        job_id = IdempotencyKey.creative_job(account_id, episode_id, prompt.prompt_id, spec)
        existing = dict(run.creative_result_snapshot or {})
        if run.creative_job_id == job_id and existing.get("status") == "SUCCEEDED" and (run.asset_id or existing.get("asset_id")):
            return {
                "job_id": job_id,
                "job_status": "SUCCEEDED",
                "creative_provider": run.creative_provider or "lechuang",
                "model": run.creative_model or prompt.recommended_model,
                "asset_id": run.asset_id or existing.get("asset_id"),
                "idempotent": True,
            }
        request_obj = PromptCompiler(self.store).to_generation_request(
            prompt,
            production_run_id=run.run_id,
            idempotency_key=job_id,
        )
        snapshot = dict(run.creative_request_snapshot or {}) or request_obj.to_payload()
        if run.creative_job_id != job_id or not run.creative_request_snapshot:
            self.store.save_production_run(ProductionRun(**{
                **run.__dict__,
                "prompt_id": prompt.prompt_id,
                "status": "CREATIVE_EXECUTION",
                "creative_provider": "lechuang",
                "creative_job_id": job_id,
                "creative_model": prompt.recommended_model,
                "creative_request_snapshot": snapshot,
                "creative_result_snapshot": {"status": "SUBMITTED", "provider": "lechuang", **existing},
                "updated_at": utcnow(),
            }))
        self.transition_episode(episode_id, account_id=account_id, to_status="GENERATING")
        import os
        from content.store import is_test_runtime

        live_e2e = os.getenv("MEITI_PRODUCTION_E2E", "").strip().lower() == "true"
        if not execute or (is_test_runtime() and not live_e2e):
            return {
                "job_id": job_id,
                "job_status": "SUBMITTED",
                "creative_provider": "lechuang",
                "model": prompt.recommended_model,
            }
        adapter, _provider_name = resolve_creative_provider("lechuang")
        try:
            kind = str(prompt.kind or "IMAGE").upper()
            if kind == "IMAGE_TO_VIDEO":
                source = self.store.get_media_asset(str(prompt.source_asset_id or ""))
                if source is None or not getattr(source, "path", None):
                    raise ProviderBlocked("lechuang", "IMAGE_TO_VIDEO requires a local source asset")
                snapshot["kind"] = "image_to_video"
                snapshot["generation_type"] = "image_to_video"
                snapshot["source_path"] = source.path
                snapshot["source_asset_id"] = source.asset_id
                task = adapter.generate_video(snapshot)
            elif kind == "VIDEO":
                snapshot["kind"] = "generate_video"
                snapshot["generation_type"] = "video"
                task = adapter.generate_video(snapshot)
            elif kind == "IMAGE":
                task = adapter.generate_image(snapshot)
            else:
                raise UnsupportedCapability(kind.lower(), provider="lechuang")
            return self._commit_generation_task(
                run=run,
                job_id=job_id,
                prompt=prompt,
                adapter=adapter,
                task=task,
                account=account,
                episode_id=episode_id,
            )
        except (AuthError, RateLimited, ProviderBlocked) as exc:
            retryable = bool(getattr(exc, "retryable", False) or (getattr(exc, "details", {}) or {}).get("retryable"))
            live = self.store.get_production_run(run.run_id) or run
            self.store.save_production_run(ProductionRun(**{
                **live.__dict__,
                "status": "BLOCKED",
                "creative_result_snapshot": {
                    "status": "FAILED",
                    "error_code": getattr(exc, "code", None) or type(exc).__name__,
                    "error_message": str(exc),
                    "retryable": retryable,
                },
                "updated_at": utcnow(),
            }))
            return {
                "job_id": job_id,
                "job_status": "FAILED",
                "creative_provider": "lechuang",
                "model": prompt.recommended_model,
                "error": str(exc),
                "retryable": retryable,
            }
        except UnsupportedCapability as exc:
            live = self.store.get_production_run(run.run_id) or run
            self.store.save_production_run(ProductionRun(**{
                **live.__dict__,
                "status": "BLOCKED",
                "creative_result_snapshot": {"status": "FAILED", "error_code": "UNSUPPORTED", "error_message": str(exc)},
                "updated_at": utcnow(),
            }))
            return {
                "job_id": job_id,
                "job_status": "FAILED",
                "creative_provider": "lechuang",
                "model": prompt.recommended_model,
                "error": str(exc),
            }

    def _commit_generation_task(self, *, run, job_id: str, prompt, adapter, task, account, episode_id: str) -> dict[str, Any]:
        status = map_creative_status(task.status)
        result = dict(task.result or {})
        live = self.store.get_production_run(run.run_id) or run
        self.store.save_production_run(ProductionRun(**{
            **live.__dict__,
            "creative_result_snapshot": {
                "status": status,
                "provider": "lechuang",
                "provider_task_id": task.provider_task_id,
                "model": result.get("model") or prompt.recommended_model,
                "cost_status": result.get("cost_status") or "UNKNOWN",
                "cost_snapshot": result.get("cost_snapshot") or {"status": "UNKNOWN"},
                "path": result.get("path") or getattr(result.get("asset"), "path", None),
                "sha256": result.get("sha256") or getattr(result.get("asset"), "sha256", None),
                "source_url": result.get("source_url") or "",
                "error": task.error,
            },
            "updated_at": utcnow(),
        }))
        if status in {"SUBMITTED", "QUEUED", "RUNNING"}:
            return {
                "job_id": job_id,
                "job_status": status,
                "creative_provider": "lechuang",
                "model": result.get("model") or prompt.recommended_model,
                "provider_task_id": task.provider_task_id,
            }
        if status != "SUCCEEDED":
            self.store.save_production_run(ProductionRun(**{
                **(self.store.get_production_run(run.run_id) or live).__dict__,
                "status": "BLOCKED",
                "updated_at": utcnow(),
            }))
            return {
                "job_id": job_id,
                "job_status": status,
                "creative_provider": "lechuang",
                "model": prompt.recommended_model,
                "error": task.error,
            }
        artifact = adapter.download_artifact(task)
        imported = self.import_asset(
            artifact.path,
            account_id=account.account_id,
            platform=account.platform,
            episode_id=episode_id,
            asset_role="GENERATED_PRIMARY",
            reuse_mode="NONE",
            intent="GENERATE",
            prompt_id=prompt.prompt_id,
            model=str(result.get("model") or prompt.recommended_model or "UNKNOWN"),
            tool="lechuang",
            generation_mode="PROVIDER_API",
            production_run_id=run.run_id,
            source_asset_id=prompt.source_asset_id,
        )
        asset = imported["asset"]
        live = self.store.get_production_run(run.run_id) or live
        self.store.save_production_run(ProductionRun(**{
            **live.__dict__,
            "asset_id": asset.asset_id,
            "creative_result_snapshot": {
                **dict(live.creative_result_snapshot or {}),
                "status": "SUCCEEDED",
                "asset_id": asset.asset_id,
                "sha256": asset.sha256,
                "provider_artifact_id": artifact.provider_artifact_id,
                "source_url": artifact.source_url,
                "mime_type": artifact.mime_type,
                "byte_size": artifact.byte_size,
            },
            "updated_at": utcnow(),
        }))
        return {
            "job_id": job_id,
            "job_status": "SUCCEEDED",
            "creative_provider": "lechuang",
            "model": str(result.get("model") or prompt.recommended_model),
            "asset_id": asset.asset_id,
            "sha256": asset.sha256,
            "qa": imported.get("qa"),
        }

    def reconcile_creative_jobs(self, *, account_id: str | None = None) -> list[dict[str, Any]]:
        from creative.errors import AuthError, ProviderBlocked, RateLimited
        from integrations.providers.resolver import resolve_creative_provider

        rows = []
        adapter, _name = resolve_creative_provider("lechuang")
        for run in self.store.list_production_runs(account_id=account_id):
            snapshot = dict(run.creative_result_snapshot or {})
            status = str(snapshot.get("status") or "")
            if run.status != "CREATIVE_EXECUTION" and status not in {"SUBMITTED", "QUEUED", "RUNNING"}:
                continue
            if not run.prompt_id or not run.episode_id:
                continue
            prompt = self.store.get_prompt(run.prompt_id)
            if prompt is None:
                continue
            provider_task_id = str(snapshot.get("provider_task_id") or "")
            if provider_task_id:
                account = self.store.get_account(run.account_id)
                if account is None:
                    continue
                try:
                    if str(prompt.kind or "").upper() in {"VIDEO", "IMAGE_TO_VIDEO"}:
                        task = adapter.client.poll_video(provider_task_id, wait=False)
                    else:
                        task = adapter.get_task(provider_task_id)
                    rows.append(self._commit_generation_task(
                        run=run,
                        job_id=run.creative_job_id or "",
                        prompt=prompt,
                        adapter=adapter,
                        task=task,
                        account=account,
                        episode_id=run.episode_id,
                    ))
                except (AuthError, RateLimited, ProviderBlocked) as exc:
                    retryable = bool(getattr(exc, "retryable", False) or (getattr(exc, "details", {}) or {}).get("retryable"))
                    self.store.save_production_run(ProductionRun(**{
                        **run.__dict__,
                        "status": "BLOCKED",
                        "creative_result_snapshot": {
                            **snapshot,
                            "status": "FAILED",
                            "error_code": getattr(exc, "code", None) or type(exc).__name__,
                            "error_message": str(exc),
                            "retryable": retryable,
                        },
                        "updated_at": utcnow(),
                    }))
                    rows.append({
                        "job_id": run.creative_job_id,
                        "job_status": "FAILED",
                        "error": str(exc),
                        "retryable": retryable,
                    })
                continue
            rows.append(self.submit_generation(
                account_id=run.account_id,
                episode_id=run.episode_id,
                prompt=prompt,
                request=run.request,
            ))
        return rows

    def import_asset(self, path: str, **fields: Any) -> dict[str, Any]:
        imported = PlatformAssetService(self.store).import_asset(path, **fields)
        account_id = str(fields.get("account_id") or "")
        episode_id = fields.get("episode_id")
        asset = imported.get("asset")
        qa = imported.get("qa") or {}
        asset_id = getattr(asset, "asset_id", None)
        episode = self.store.get_episode(episode_id, account_id=account_id) if episode_id and account_id else None
        tasks = TaskOS(self.store)
        tasks.complete_type(account_id=account_id, episode_id=episode_id, task_type="CREATIVE_EXECUTION", asset_id=asset_id)
        tasks.complete_type(account_id=account_id, episode_id=episode_id, task_type="ASSET_IMPORT", asset_id=asset_id)
        if qa.get("decision") == "pass":
            tasks.complete_type(account_id=account_id, episode_id=episode_id, task_type="QA", asset_id=asset_id)
            self.record_evidence(
                kind="QA_PASSED",
                account_id=account_id,
                platform=str(fields.get("platform") or ""),
                episode_id=episode_id,
                prompt_id=fields.get("prompt_id"),
                asset_id=asset_id,
                production_run_id=episode.production_run_id if episode else None,
                source="lechuang",
                detail={"qa": qa.get("decision")},
            )
        current = tasks.get_next_action(account_id=account_id)
        account = self.store.get_account(account_id) if account_id else None
        if account is not None:
            sync_operating_state(
                self.store,
                account_id=account_id,
                platform=account.platform,
                current_episode=episode_id,
                current_task=current.task_id if current else None,
                last_generated_asset=asset_id,
                current_content_status="QA_PASSED" if qa.get("decision") == "pass" else "QA_FAILED",
                next_action=current.task_type if current else "PACKAGE",
            )
        return imported

    def package_from_generation(self, *, context, assets: list[Any], title: str = "", body: str = "", package_id: str | None = None, status: str = "GENERATED", prompt_id: str | None = None, reference_assets: tuple[str, ...] = ()) -> ContentPackage:
        from content.assets import REFERENCE_ROLES

        paths = tuple(getattr(item, "path", item) for item in assets if item)
        primary_ids = []
        reference_ids = list(reference_assets)
        for item in assets:
            if item is None:
                continue
            role = str(getattr(item, "asset_role", "") or "GENERATED_PRIMARY").upper()
            asset_id = str(getattr(item, "asset_id", "") or getattr(item, "path", "") or "")
            if not asset_id:
                continue
            if role in REFERENCE_ROLES:
                if asset_id not in reference_ids:
                    reference_ids.append(asset_id)
                continue
            primary_ids.append(asset_id)
        if len(primary_ids) > 1:
            raise ConfigurationBlocked("UNIQUE_PRIMARY_REQUIRED", "package requires exactly one primary asset")
        episode = self.store.get_episode(context.episode_id, account_id=context.account_id) if context.episode_id else None
        package = ContentPackage(
            package_id=package_id or uuid4().hex,
            title=title or context.creative_request or context.user_request,
            body=body or context.normalized_prompt,
            media_assets=tuple(primary_ids) or paths,
            created_at=utcnow(),
            updated_at=utcnow(),
            status=status,
            account_id=context.account_id,
            series_id=context.series_id,
            episode_id=context.episode_id,
            platform=context.platform,
            character_id=context.character_id,
            world_id=context.world_id,
            creative_context_id=context.context_id,
            reference_assets=tuple(reference_ids),
            primary_assets=tuple(primary_ids),
            prompt_id=prompt_id,
            content_decision_id=episode.content_decision_id if episode else None,
        )
        package = differentiate_package(package, context)
        saved = self.store.save_package(package)
        revision = self.store.save_package_snapshot(saved, change_summary=f"{status} v{saved.revision}")
        package = ContentPackage(**{**saved.__dict__, "revision": revision.version, "current_revision": revision.revision_id})
        from content.assets import PlatformAssetService
        service = PlatformAssetService(self.store)
        for item in assets:
            if item is None:
                continue
            role = str(getattr(item, "asset_role", "") or "GENERATED_PRIMARY").upper()
            mapped_role = "REFERENCE" if role in REFERENCE_ROLES else "PRIMARY"
            if getattr(item, "asset_id", None):
                service.map_package_asset(package, item, role=mapped_role, selected=mapped_role == "PRIMARY")
        if context.episode_id:
            episode = self.store.get_episode(context.episode_id, account_id=context.account_id)
            if episode is not None:
                next_status = "PACKAGE_READY" if primary_ids else status
                self.store.save_episode(Episode(**{**episode.__dict__, "content_package_id": package.package_id, "content_status": next_status, "updated_at": utcnow()}))
                self.record_evidence(
                    kind="PACKAGE_READY",
                    account_id=context.account_id,
                    platform=context.platform,
                    episode_id=context.episode_id,
                    package_id=package.package_id,
                    prompt_id=prompt_id,
                    asset_id=primary_ids[0] if primary_ids else None,
                )
                TaskOS(self.store).complete_type(
                    account_id=context.account_id,
                    episode_id=context.episode_id,
                    task_type="PACKAGE",
                    package_id=package.package_id,
                    prompt_id=prompt_id,
                    asset_id=primary_ids[0] if primary_ids else None,
                )
                if episode.production_run_id:
                    run = self.store.get_production_run(episode.production_run_id)
                    if run is not None:
                        self.store.save_production_run(ProductionRun(**{
                            **run.__dict__,
                            "package_id": package.package_id,
                            "asset_id": primary_ids[0] if primary_ids else run.asset_id,
                            "prompt_id": prompt_id or run.prompt_id,
                            "status": "PACKAGE_READY",
                            "updated_at": utcnow(),
                        }))
                current = TaskOS(self.store).get_next_action(account_id=context.account_id)
                sync_operating_state(
                    self.store,
                    account_id=context.account_id,
                    platform=context.platform,
                    current_episode=context.episode_id,
                    current_task=current.task_id if current else None,
                    current_content_status="PACKAGE_READY",
                    next_action=current.task_type if current else "HANDOFF",
                )
                EpisodePlanner(self.store).ensure_calendar(
                    account_id=context.account_id,
                    date=today_iso(),
                    topic=package.title,
                    episode_id=context.episode_id,
                    task_id=current.task_id if current else None,
                    status="READY_TO_PUBLISH",
                    slot=context.episode_id or "default",
                )
        return package

    def record_lineage(
        self,
        *,
        asset,
        context,
        attempt_no: int | None = None,
        parent_asset_id: str | None = None,
        qa_decision: str = "",
        provider: str = "",
        provider_task_id: str = "",
        model: str = "",
        package_id: str | None = None,
    ) -> AssetLineage:
        asset_id = getattr(asset, "asset_id", None) or str(asset)
        if provider or provider_task_id or model:
            self.store.save_context(replace(
                context,
                provider=provider or context.provider,
                provider_task_id=provider_task_id or context.provider_task_id,
                model=model or context.model,
            ))
        lineage = AssetLineage(
            lineage_id=uuid4().hex,
            asset_id=asset_id,
            account_id=context.account_id,
            series_id=context.series_id,
            episode_id=context.episode_id,
            content_package_id=package_id,
            creative_context_id=context.context_id,
            character_id=context.character_id,
            world_id=context.world_id,
            user_request=context.user_request,
            generation_request={
                "prompt": context.normalized_prompt,
                "creative_request": context.creative_request,
                "parameters": dict(context.generation_parameters),
            },
            provider=provider or context.provider,
            provider_task_id=provider_task_id or context.provider_task_id,
            model=model or context.model,
            attempt_no=attempt_no or 1,
            parent_asset_id=parent_asset_id,
            qa_decision=qa_decision,
            source_asset_id=parent_asset_id,
            workflow_id=str((context.generation_parameters or {}).get("workflow_id") or ""),
        )
        if attempt_no is None:
            return self.store.allocate_attempt(
                account_id=context.account_id,
                episode_id=context.episode_id,
                parent_asset_id=parent_asset_id,
                lineage=lineage,
            )
        return self.store.save_lineage(lineage)

    def record_publication(self, *, package: ContentPackage, publication) -> ContinuityMemory:
        publication_id = getattr(publication, "publication_id", "") or ""
        if not package.account_id:
            return ContinuityMemory(memory_id="none", kind="episode", account_id="", subject_id="", key="published", value={})
        canonical = ContinuityMemory(
            memory_id=uuid4().hex,
            kind="episode",
            account_id=package.account_id,
            subject_id=package.episode_id or package.package_id,
            key="published",
            value={
                "published_at": getattr(publication, "published_at", None),
                "platform": getattr(publication, "platform", package.platform),
                "account": package.account_id,
                "content_package": package.package_id,
                "media_asset_ids": list(package.media_assets),
                "publication_id": publication_id,
                "external_post_id": getattr(publication, "provider_post_id", ""),
                "publication_url": getattr(publication, "external_url", ""),
                "projection": "PROJECTION_PENDING",
            },
        )
        with self.store.transaction():
            self.store.save_memory(canonical)
            if package.episode_id:
                episode = self.store.get_episode(package.episode_id, account_id=package.account_id)
                if episode is not None:
                    self.store.save_episode(Episode(**{**episode.__dict__, "content_status": "PUBLISHED", "updated_at": utcnow()}))
                    if episode.production_run_id:
                        run = self.store.get_production_run(episode.production_run_id)
                        if run is not None:
                            self.store.save_production_run(ProductionRun(**{
                                **run.__dict__,
                                "publication_id": publication_id or run.publication_id,
                                "package_id": package.package_id,
                                "status": "PUBLISHED",
                                "updated_at": utcnow(),
                            }))
            selected = {str(item) for item in package.media_assets}
            for lineage in self.store.list_lineage(account_id=package.account_id, episode_id=package.episode_id):
                chosen = (
                    lineage.asset_id in selected
                    or lineage.content_package_id == package.package_id
                    or lineage.selected_for_package
                )
                if chosen:
                    self.store.save_lineage(replace(
                        lineage,
                        published=True,
                        selected_for_package=True,
                        content_package_id=package.package_id,
                    ))
            for asset_id in selected:
                lineage = self.store.get_lineage(asset_id, account_id=package.account_id)
                if lineage is not None:
                    self.store.save_lineage(replace(lineage, published=True, selected_for_package=True, content_package_id=package.package_id))
            sync_operating_state(
                self.store,
                account_id=package.account_id,
                platform=package.platform,
                current_episode=package.episode_id,
                last_published_episode=package.episode_id,
                current_content_status="PUBLISHED",
                next_action="ANALYTICS",
            )
        projection = "PROJECTED"
        try:
            from memory.service import get_memory_service
            get_memory_service().writeback({
                "kind": "PUBLICATION_LEARNING",
                "account_id": package.account_id,
                "platform": package.platform,
                "series_id": package.series_id,
                "episode_id": package.episode_id,
                "publication_id": publication_id,
                "source": "publication",
                "content_pattern": {
                    "package_id": package.package_id,
                    "media_asset_ids": list(package.media_assets),
                },
            })
        except Exception:
            projection = "PROJECTION_PENDING"
        memories = self.store.list_memories(account_id=package.account_id, kind="episode")
        published = [item for item in memories if item.key == "published"]
        if published:
            latest = published[-1]
            if projection == "PROJECTED":
                latest = ContinuityMemory(**{**latest.__dict__, "value": {**dict(latest.value or {}), "projection": "PROJECTED"}})
                self.store.save_memory(latest)
            return latest
        return ContinuityMemory(**{**canonical.__dict__, "value": {**dict(canonical.value or {}), "projection": projection}})

    def record_feedback(self, feedback: PerformanceFeedback) -> PerformanceFeedback:
        return self.store.save_feedback(feedback)

    def calendar(self, *, account_id: str | None = None) -> list[dict[str, Any]]:
        entries = self.store.list_calendar(account_id=account_id)
        if entries:
            rows = []
            for item in entries:
                episode = self.store.get_episode(item.episode_id, account_id=item.account_id) if item.episode_id else None
                published = item.status == "PUBLISHED" or bool(episode and episode.content_status == "PUBLISHED")
                rows.append({
                    "calendar_id": item.calendar_id,
                    "platform": item.platform,
                    "account_id": item.account_id,
                    "date": item.date,
                    "slot": item.slot,
                    "topic": item.topic,
                    "format": item.format,
                    "status": "PUBLISHED" if published else item.status,
                    "episode_id": item.episode_id,
                    "task_id": item.task_id,
                    "priority": item.priority,
                    "published": published,
                    "content_status": episode.content_status if episode else item.status,
                    "display_name": "",
                    "series": "",
                    "episode_no": episode.episode_no if episode else 0,
                    "generated": bool(episode and episode.content_package_id),
                    "failed": bool(episode and episode.content_status == "FAILED"),
                })
            return rows
        rows = []
        accounts = [self.store.get_account(account_id)] if account_id else self.store.list_accounts()
        for account in accounts:
            if account is None:
                continue
            series = self.store.active_series(account.account_id)
            episode = self.store.latest_episode(series.series_id) if series else None
            rows.append({
                "platform": account.platform,
                "account_id": account.account_id,
                "display_name": account.display_name,
                "series": series.name if series else "",
                "episode_no": episode.episode_no if episode else 0,
                "content_status": episode.content_status if episode else "IDEA",
                "generated": bool(episode and episode.content_package_id),
                "published": bool(episode and episode.content_status == "PUBLISHED"),
                "failed": bool(episode and episode.content_status == "FAILED"),
            })
        return rows

    def show_account(self, account_id: str) -> dict[str, Any]:
        account = self.store.get_account(account_id)
        if account is None:
            raise KeyError(account_id)
        character = self.store.get_character(account.character_id, account_id=account.account_id) if account.character_id else None
        world = self.store.get_world(account.world_id, account_id=account.account_id) if account.world_id else None
        series = self.store.active_series(account.account_id)
        episode = self.store.latest_episode(series.series_id) if series else None
        profile = self.store.get_account_profile(account_id)
        state = self.store.get_operating_state(account_id)
        creator_state = self.store.get_creator_state(account_id)
        strategy = self.store.current_strategy(account_id)
        connection = self.store.get_platform_connection(account_id, account.platform)
        next_action = TaskOS(self.store).get_next_action(account_id=account_id)
        return {
            "account": account,
            "character": character,
            "world": world,
            "series": series,
            "episode": episode,
            "profile": profile,
            "operating_state": state,
            "creator_state": creator_state,
            "strategy": strategy,
            "connection": connection,
            "current_task": next_action,
        }

    def history(self, account_id: str) -> dict[str, Any]:
        account = self.store.get_account(account_id)
        if account is None:
            raise KeyError(account_id)
        series_list = self.store.list_series(account_id)
        episodes = []
        for series in series_list:
            episodes.extend(self.store.list_episodes(series.series_id))
        return {
            "account": account,
            "series": series_list,
            "episodes": episodes,
            "memories": self.store.list_memories(account_id=account_id),
            "lineage": self.store.list_lineage(account_id=account_id),
            "feedback": self.store.list_feedback(account_id),
        }

    def open_production_run(
        self,
        *,
        account_id: str,
        platform: str,
        episode_id: str | None = None,
        request: str = "",
        run_id: str | None = None,
    ) -> ProductionRun:
        if episode_id:
            episode = self.store.get_episode(episode_id, account_id=account_id)
            if episode and episode.production_run_id:
                existing = self.store.get_production_run(episode.production_run_id)
                if existing is not None:
                    return existing
        run = ProductionRun(
            run_id=run_id or uuid4().hex,
            account_id=account_id,
            platform=platform,
            episode_id=episode_id,
            request=request,
            status="CREATED",
        )
        saved = self.store.save_production_run(run)
        if episode_id:
            episode = self.store.get_episode(episode_id, account_id=account_id)
            if episode is not None:
                self.store.save_episode(Episode(**{**episode.__dict__, "production_run_id": saved.run_id, "updated_at": utcnow()}))
        return saved

    def record_evidence(self, *, kind: str, account_id: str, platform: str, status: str = "PASS", source: str = "operator", **fields: Any) -> ProductionEvidence:
        evidence = ProductionEvidence(
            evidence_id=uuid4().hex,
            kind=kind,
            account_id=account_id,
            platform=platform,
            status=status,
            source=source,
            episode_id=fields.get("episode_id"),
            prompt_id=fields.get("prompt_id"),
            asset_id=fields.get("asset_id"),
            package_id=fields.get("package_id"),
            handoff_id=fields.get("handoff_id"),
            publication_id=fields.get("publication_id"),
            analytics_id=fields.get("analytics_id"),
            learning_id=fields.get("learning_id"),
            production_run_id=fields.get("production_run_id"),
            detail=dict(fields.get("detail") or {}),
        )
        return self.store.save_evidence(evidence)

    def transition_episode(self, episode_id: str, *, account_id: str, to_status: str, evidence_id: str | None = None) -> Episode:
        episode = self.store.get_episode(episode_id, account_id=account_id)
        if episode is None:
            raise IsolationError(f"episode {episode_id} is not owned by {account_id}")
        if to_status not in LIFECYCLE_OWNERS and to_status not in {
            "IDEA", "BRIEFED", "DRAFT", "PROMPT_READY", "AWAITING_CREATIVE", "GENERATING", "GENERATED",
            "IMPORTED", "QA_PASSED", "QA_FAILED", "PACKAGE_READY", "HANDOFF_READY", "READY_TO_PUBLISH",
            "APPROVED", "PUBLISHED", "ANALYTICS_PENDING", "LEARNED", "FAILED", "REJECTED", "ARCHIVED",
        }:
            raise ValueError(f"invalid content status: {to_status}")
        if episode.content_status != to_status:
            self.store.save_lifecycle(LifecycleTransition(
                transition_id=uuid4().hex,
                episode_id=episode_id,
                account_id=account_id,
                from_status=episode.content_status,
                to_status=to_status,
                owner=LIFECYCLE_OWNERS.get(to_status, "content-agent"),
                evidence_id=evidence_id,
            ))
        return self.store.save_episode(Episode(**{**episode.__dict__, "content_status": to_status, "updated_at": utcnow()}))

    def record_handoff(self, *, package: ContentPackage, handoff) -> ProductionEvidence:
        if not package.account_id:
            raise IsolationError("handoff requires account_id")
        run = None
        with self.store.transaction():
            if package.episode_id:
                self.transition_episode(package.episode_id, account_id=package.account_id, to_status="HANDOFF_READY")
                episode = self.store.get_episode(package.episode_id, account_id=package.account_id)
                if episode and episode.production_run_id:
                    run = self.store.get_production_run(episode.production_run_id)
            if run is not None:
                self.store.save_production_run(ProductionRun(**{
                    **run.__dict__,
                    "package_id": package.package_id,
                    "handoff_id": getattr(handoff, "handoff_id", None),
                    "status": "HANDED_OFF",
                    "updated_at": utcnow(),
                }))
            TaskOS(self.store).complete_type(
                account_id=package.account_id,
                episode_id=package.episode_id,
                task_type="HANDOFF",
                package_id=package.package_id,
            )
            current = TaskOS(self.store).get_next_action(account_id=package.account_id)
            sync_operating_state(
                self.store,
                account_id=package.account_id,
                platform=package.platform,
                current_episode=package.episode_id,
                current_task=current.task_id if current else None,
                current_content_status="HANDOFF_READY",
                next_action=current.task_type if current else "ANALYTICS",
            )
            EpisodePlanner(self.store).ensure_calendar(
                account_id=package.account_id,
                date=today_iso(),
                topic=package.title,
                episode_id=package.episode_id,
                task_id=current.task_id if current else None,
                status="READY_TO_PUBLISH",
                slot=package.episode_id or "default",
            )
            return self.record_evidence(
                kind="XHS_HANDOFF" if package.platform == "xiaohongshu" else "HANDOFF",
                account_id=package.account_id,
                platform=package.platform,
                episode_id=package.episode_id,
                package_id=package.package_id,
                prompt_id=package.prompt_id,
                handoff_id=getattr(handoff, "handoff_id", None),
                production_run_id=run.run_id if run else None,
                source="operator",
                detail={"kind": "handoff", "status": getattr(handoff, "status", ""), "published": False},
            )

    def record_analytics(self, record: AnalyticsRecord) -> AnalyticsRecord:
        if not record.episode_id:
            raise ConfigurationBlocked("ANALYTICS_EPISODE_REQUIRED", "analytics must bind an episode")
        saved = self.store.save_analytics(record)
        verified = saved.origin == "PROVIDER" and saved.verification_status == "VERIFIED"
        kind = "ANALYTICS_IMPORTED" if verified else "MANUAL_ANALYTICS_OBSERVATION"
        episode = self.store.get_episode(saved.episode_id, account_id=saved.account_id)
        if episode is not None:
            self.transition_episode(saved.episode_id, account_id=saved.account_id, to_status="ANALYTICS_PENDING")
            if episode.production_run_id:
                run = self.store.get_production_run(episode.production_run_id)
                if run is not None:
                    self.store.save_production_run(ProductionRun(**{
                        **run.__dict__,
                        "analytics_id": saved.analytics_id,
                        "status": "ANALYTICS_CAPTURED",
                        "updated_at": utcnow(),
                    }))
        TaskOS(self.store).complete_type(
            account_id=saved.account_id,
            episode_id=saved.episode_id,
            task_type="ANALYTICS",
        )
        self.record_evidence(
            kind=kind,
            account_id=saved.account_id,
            platform=saved.platform,
            episode_id=saved.episode_id,
            package_id=saved.package_id,
            handoff_id=saved.handoff_id,
            publication_id=saved.publication_id,
            analytics_id=saved.analytics_id,
            source="analytics",
            detail={
                "origin": saved.origin,
                "verification_status": saved.verification_status,
                "verified": verified,
            },
        )
        current = TaskOS(self.store).get_next_action(account_id=saved.account_id)
        sync_operating_state(
            self.store,
            account_id=saved.account_id,
            platform=saved.platform,
            current_episode=saved.episode_id,
            current_task=current.task_id if current else None,
            current_content_status="ANALYTICS_PENDING",
            next_action=current.task_type if current else "LEARNING",
        )
        return saved

    def record_learning(self, record: LearningRecord) -> LearningRecord:
        source_episodes = record.source_episode_ids or ((record.episode_id,) if record.episode_id else ())
        analytics = self.store.get_analytics(record.analytics_id) if record.analytics_id else None
        provider_verified = bool(
            analytics is not None
            and analytics.origin == "PROVIDER"
            and analytics.verification_status == "VERIFIED"
            and analytics.publication_id
            and analytics.provider_payload
        )
        evidence_status = record.evidence_status
        if evidence_status == "VERIFIED":
            if analytics is None or not record.episode_id:
                evidence_status = "NOT_ENOUGH_EVIDENCE"
            elif not provider_verified:
                evidence_status = "NOT_ENOUGH_EVIDENCE"
        elif analytics is not None and not provider_verified and evidence_status == "NOT_VERIFIED":
            evidence_status = "NOT_ENOUGH_EVIDENCE"
        saved = self.store.save_learning(LearningRecord(**{
            **record.__dict__,
            "evidence_status": evidence_status,
            "learning_status": evidence_status,
            "source_episode_ids": source_episodes,
        }))
        verified = saved.evidence_status == "VERIFIED"
        if verified:
            profile = self.store.get_learning_profile(saved.account_id, saved.platform)
            if profile is not None:
                worked = tuple(dict.fromkeys(list(profile.successful_patterns) + ([saved.what_worked] if saved.what_worked else [])))
                failed = tuple(dict.fromkeys(list(profile.failed_patterns) + ([saved.what_failed] if saved.what_failed else [])))
                recs = tuple(dict.fromkeys(list(profile.prompt_patterns) + ([saved.next_recommendation] if saved.next_recommendation else [])))
                self.store.save_learning_profile(PlatformLearningProfile(**{
                    **profile.__dict__,
                    "successful_patterns": worked,
                    "failed_patterns": failed,
                    "prompt_patterns": recs,
                    "updated_at": utcnow(),
                }))
            projection = "PROJECTED"
            try:
                from memory.service import get_memory_service
                get_memory_service().writeback({
                    "kind": "LEARNING_RECORD",
                    "account_id": saved.account_id,
                    "platform": saved.platform,
                    "episode_id": saved.episode_id,
                    "source": "analytics",
                    "evidence_status": saved.evidence_status,
                    "successful_pattern": {
                        "what_worked": saved.what_worked,
                        "visual_learning": saved.visual_learning,
                        "prompt_learning": saved.prompt_learning,
                        "reason": saved.reason,
                        "next_recommendation": saved.next_recommendation,
                        "source_episode_ids": list(saved.source_episode_ids),
                    },
                    "content_pattern": {
                        "content_learning": saved.content_learning,
                        "audience_learning": saved.audience_learning,
                    },
                })
            except Exception:
                projection = "PROJECTION_PENDING"
            if saved.episode_id:
                self.transition_episode(saved.episode_id, account_id=saved.account_id, to_status="LEARNED")
            TaskOS(self.store).complete_type(
                account_id=saved.account_id,
                episode_id=saved.episode_id,
                task_type="LEARNING",
            )
            episode = self.store.get_episode(saved.episode_id, account_id=saved.account_id) if saved.episode_id else None
            if episode and episode.production_run_id:
                run = self.store.get_production_run(episode.production_run_id)
                if run is not None:
                    closed = bool(run.publication_id and run.analytics_id)
                    self.store.save_production_run(ProductionRun(**{
                        **run.__dict__,
                        "learning_id": saved.learning_id,
                        "status": "CLOSED" if closed else "LEARNING_VERIFIED",
                        "updated_at": utcnow(),
                    }))
            sync_operating_state(
                self.store,
                account_id=saved.account_id,
                platform=saved.platform,
                last_learning=saved.learning_id,
                learning_summary=saved.next_recommendation or saved.what_worked or saved.reason,
                current_content_status="LEARNED",
                next_action="CONTENT_PLAN",
            )
        else:
            projection = "PENDING_OBSERVATION"
        self.record_evidence(
            kind="LEARNING_WRITTEN" if verified else "LEARNING_PENDING",
            account_id=saved.account_id,
            platform=saved.platform,
            episode_id=saved.episode_id,
            analytics_id=saved.analytics_id,
            learning_id=saved.learning_id,
            prompt_id=saved.prompt_id,
            asset_id=saved.asset_id,
            source="memory" if verified else "operator",
            detail={
                "reason": saved.reason,
                "next_recommendation": saved.next_recommendation,
                "evidence_status": saved.evidence_status,
                "projection": projection,
            },
        )
        return saved

    def promote_pattern(
        self,
        pattern: PromptPattern,
        *,
        status: str,
        sample_count: int,
        cross_platform_evidence: tuple[str, ...] = (),
        confidence: float = 0.0,
        reason: str = "",
    ) -> PatternPromotion:
        if status in {"GLOBAL_CANDIDATE", "GLOBAL_PATTERN"}:
            if int(sample_count or 0) < 2 or not cross_platform_evidence:
                raise ConfigurationBlocked("PROMOTION_EVIDENCE_MISSING", "GLOBAL promotion requires sample_count and cross-platform evidence")
        saved_pattern = self.store.save_prompt_pattern(PromptPattern(**{
            **pattern.__dict__,
            "promotion_status": status,
            "sample_count": sample_count,
            "global_pattern": status == "GLOBAL_PATTERN",
            "platform": "GLOBAL" if status == "GLOBAL_PATTERN" else pattern.platform,
            "updated_at": utcnow(),
        }))
        return self.store.save_pattern_promotion(PatternPromotion(
            promotion_id=uuid4().hex,
            pattern_id=saved_pattern.pattern_id,
            platform=saved_pattern.platform,
            status=status,
            sample_count=sample_count,
            cross_platform_evidence=tuple(cross_platform_evidence),
            confidence=confidence,
            reason=reason,
        ))

    def _sync_profile(self, account_id: str, **fields: Any) -> AccountProfile:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        current = self.store.get_account_profile(account_id)
        if current is None:
            current = AccountProfile(
                account_id=account.account_id,
                platform=account.platform,
                display_name=account.display_name,
                external_account_id=account.external_account_id,
                status=account.status,
                character_id=account.character_id,
                world_id=account.world_id,
                series_id=account.series_id,
            )
        payload = {**current.__dict__, **{key: value for key, value in fields.items() if value is not None}, "updated_at": utcnow()}
        payload.setdefault("display_name", account.display_name)
        payload.setdefault("status", account.status)
        payload.setdefault("character_id", account.character_id)
        payload.setdefault("world_id", account.world_id)
        payload.setdefault("series_id", account.series_id)
        return self.store.save_account_profile(AccountProfile(**payload))

    def override_profile(
        self,
        account_id: str,
        *,
        field_name: str,
        value: Any,
        reason: str,
        changed_by: str = "operator",
    ) -> AccountProfile:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        profile = self.store.get_account_profile(account_id) or self._sync_profile(account_id)
        if field_name not in PROFILE_KNOWLEDGE_FIELDS:
            raise ConfigurationBlocked("UNKNOWN_PROFILE_FIELD", f"cannot override {field_name}")
        old = getattr(profile, field_name)
        old_value = old.value if isinstance(old, KnowledgeField) else old
        field = knowledge_field(value, source="USER_OVERRIDE", reason=reason, changed_by=changed_by)
        saved = self.store.save_account_profile(AccountProfile(**{**profile.__dict__, field_name: field, "updated_at": utcnow()}))
        self.store.save_override(ManualOverride(
            override_id=uuid4().hex,
            account_id=account_id,
            platform=account.platform,
            target_kind="account_profile",
            target_id=account_id,
            field_name=field_name,
            old_value=old_value,
            new_value=value,
            changed_by=changed_by,
            reason=reason,
            source="USER_OVERRIDE",
        ))
        return saved

    def override_world(
        self,
        account_id: str,
        *,
        field_name: str,
        value: Any,
        reason: str,
        changed_by: str = "operator",
    ) -> AccountWorld:
        account = self.store.get_account(account_id)
        if account is None or not account.world_id:
            raise IsolationError("world override requires a bound world")
        world = self.store.get_world(account.world_id, account_id=account_id)
        if world is None:
            raise IsolationError("world not found")
        if not hasattr(world, field_name):
            raise ConfigurationBlocked("UNKNOWN_WORLD_FIELD", f"cannot override {field_name}")
        old_value = getattr(world, field_name)
        next_version = int(world.version or 1) + 1
        payload = {**world.__dict__, field_name: value, "version": next_version, "updated_at": utcnow()}
        saved = self.store.save_world(AccountWorld(**payload))
        self.store.save_world_revision(WorldRevision(
            revision_id=uuid4().hex,
            world_id=saved.world_id,
            account_id=account_id,
            version=saved.version,
            snapshot={"name": saved.name, "city": saved.city, field_name: value},
        ))
        self.store.save_override(ManualOverride(
            override_id=uuid4().hex,
            account_id=account_id,
            platform=account.platform,
            target_kind="world",
            target_id=saved.world_id,
            field_name=field_name,
            old_value=old_value,
            new_value=value,
            changed_by=changed_by,
            reason=reason,
            source="USER_OVERRIDE",
        ))
        return saved

    def override_character(
        self,
        account_id: str,
        *,
        field_name: str,
        value: Any,
        reason: str,
        changed_by: str = "operator",
    ) -> VirtualCharacter:
        account = self.store.get_account(account_id)
        if account is None or not account.character_id:
            raise IsolationError("character override requires a bound character")
        character = self.store.get_character(account.character_id, account_id=account_id)
        if character is None:
            raise IsolationError("character not found")
        if not hasattr(character, field_name):
            raise ConfigurationBlocked("UNKNOWN_CHARACTER_FIELD", f"cannot override {field_name}")
        old_value = getattr(character, field_name)
        next_version = int(character.version or 1) + 1
        payload = {**character.__dict__, field_name: value, "version": next_version, "updated_at": utcnow()}
        saved = self.store.save_character(VirtualCharacter(**payload))
        self.store.save_character_revision(CharacterRevision(
            revision_id=uuid4().hex,
            character_id=saved.character_id,
            account_id=account_id,
            version=saved.version,
            snapshot={"name": saved.name, "appearance": dict(saved.appearance_profile), field_name: value},
        ))
        self.store.save_override(ManualOverride(
            override_id=uuid4().hex,
            account_id=account_id,
            platform=account.platform,
            target_kind="character",
            target_id=saved.character_id,
            field_name=field_name,
            old_value=old_value,
            new_value=value,
            changed_by=changed_by,
            reason=reason,
            source="USER_OVERRIDE",
        ))
        return saved

    def get_today_tasks(self, *, account_id: str | None = None, platform: str | None = None) -> list[CreatorTask]:
        return TaskOS(self.store).get_today_tasks(account_id=account_id, platform=platform)

    def get_blocked_tasks(self, *, account_id: str | None = None, platform: str | None = None) -> list[CreatorTask]:
        return TaskOS(self.store).get_blocked_tasks(account_id=account_id, platform=platform)

    def get_next_action(self, *, account_id: str | None = None, platform: str | None = None, episode_id: str | None = None) -> CreatorTask | None:
        return TaskOS(self.store).get_next_action(account_id=account_id, platform=platform, episode_id=episode_id)

    def plan_next(self, *, account_id: str, request: str = "", format: str = "image"):
        return EpisodePlanner(self.store).plan_next(account_id=account_id, request=request, format=format)

    def tomorrow(self, *, account_id: str) -> dict[str, Any]:
        return EpisodePlanner(self.store).tomorrow(account_id=account_id)

    def production_readiness(self, *, account_id: str | None = None, episode_id: str | None = None, persist: bool = True) -> dict[str, Any]:
        return ProductionReadinessService(self.store).evaluate(account_id=account_id, episode_id=episode_id, persist=persist)

    def dashboard(self, *, account_id: str | None = None, platform: str | None = None) -> dict[str, Any]:
        account = self.store.get_account(account_id) if account_id else self.store.active_account(platform=platform)
        if account is None:
            account = self.store.active_account()
        if account is None:
            return {"status": "NOT_CONFIGURED", "reason": "no platform account"}
        view = self.show_account(account.account_id)
        state = view.get("operating_state")
        creator_state = view.get("creator_state")
        strategy = view.get("strategy")
        connection = view.get("connection")
        episode = view.get("episode")
        series = view.get("series")
        task = view.get("current_task") or self.get_next_action(account_id=account.account_id)
        buckets = TaskOS(self.store).classify_open_tasks(account_id=account.account_id)
        today_tasks = buckets.get("TODAY") or []
        learning = self.store.list_learning(account_id=account.account_id, platform=account.platform)
        prompt = self.store.get_prompt(episode.prompt_id) if episode and episode.prompt_id else None
        pending_creative = [item for item in buckets.get("WAITING_OPERATOR") or [] if item.task_type == "CREATIVE_EXECUTION"]
        pending_import = [item for item in (buckets.get("TODAY") or []) + (buckets.get("OVERDUE") or []) if item.task_type == "ASSET_IMPORT"]
        pending_handoff = [item for item in (buckets.get("TODAY") or []) + (buckets.get("OVERDUE") or []) if item.task_type == "HANDOFF"]
        waiting_external = buckets.get("WAITING_EXTERNAL") or []
        return {
            "account": account.label(),
            "account_id": account.account_id,
            "platform": account.platform,
            "connection_status": connection.connection_status if connection else "NOT_CONNECTED",
            "current_strategy": None if strategy is None else {"strategy_id": strategy.strategy_id, "version": strategy.version, "objective": strategy.objective},
            "creator_state": None if creator_state is None else creator_state.snapshot(),
            "current_objective": (creator_state.current_objective if creator_state else "") or (state.current_objective if state else "") or (view["profile"].field_value("account_objective") if view.get("profile") else ""),
            "current_series": series.name if series else (state.current_series if state else None),
            "current_episode": episode.title if episode else None,
            "current_episode_id": episode.episode_id if episode else None,
            "today_tasks": [{"task_id": item.task_id, "task_type": item.task_type, "status": item.status} for item in today_tasks],
            "waiting_operator": [{"task_id": item.task_id, "task_type": item.task_type, "status": item.status} for item in buckets.get("WAITING_OPERATOR") or []],
            "waiting_external": [{"task_id": item.task_id, "task_type": item.task_type, "status": item.status} for item in waiting_external],
            "current_task": None if task is None else {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "status": task.status,
                "title": task.title,
                "next_task_type": task.next_task_type,
            },
            "pending_creative": [{"task_id": item.task_id, "status": item.status, "episode_id": item.episode_id} for item in pending_creative],
            "pending_import": [{"task_id": item.task_id, "status": item.status, "episode_id": item.episode_id} for item in pending_import],
            "pending_handoff": [{"task_id": item.task_id, "status": item.status, "episode_id": item.episode_id} for item in pending_handoff],
            "recent_prompt": None if prompt is None else {"prompt_id": prompt.prompt_id, "kind": prompt.kind, "copy_ready": bool(prompt.copy_ready)},
            "recent_asset": episode.primary_asset_id if episode else None,
            "recent_learning": [{"learning_id": item.learning_id, "reason": item.reason, "next_recommendation": item.next_recommendation} for item in learning[:5]],
            "next_recommended_action": None if task is None else {
                "task_type": task.task_type,
                "status": task.status,
                "title": task.title,
            },
        }

    def seed_sandbox(self) -> dict[str, Any]:
        xhs = self._seed_platform_account(
            account_id="meiti-xhs-main",
            platform="xiaohongshu",
            display_name="meiti-xhs-main",
            character=_xhs_character("meiti-xhs-main"),
            world=_xhs_world("meiti-xhs-main"),
            series="认真生活 Day Series",
        )
        douyin = self._seed_platform_account(
            account_id="meiti-douyin-main",
            platform="douyin",
            display_name="meiti-douyin-main",
            character=_douyin_character("meiti-douyin-main"),
            world=_douyin_world("meiti-douyin-main"),
            series="训练挑战 Day Series",
        )
        return {"xiaohongshu": self.show_account(xhs.account_id), "douyin": self.show_account(douyin.account_id)}

    def _seed_platform_account(self, *, account_id: str, platform: str, display_name: str, character: VirtualCharacter, world: AccountWorld, series: str) -> PlatformAccount:
        existing = self.store.get_account(account_id)
        if existing is None:
            account = self.create_account(platform=platform, display_name=display_name, account_id=account_id)
        else:
            account = existing
        if account.character_id is None:
            self.bind_character(account.account_id, character)
        if account.world_id is None:
            self.bind_world(account.account_id, world)
        if self.store.active_series(account.account_id) is None:
            self.create_series(account_id=account.account_id, name=series)
        self.configure_identity(
            account.account_id,
            account_subject="个人创作者",
            positioning="认真生活记录" if platform == "xiaohongshu" else "训练状态记录",
            target_audience="都市年轻女性" if platform == "xiaohongshu" else "训练人群",
            content_pillars=("日常记录", "人物状态", "生活场景", "关系互动", "Experiment"),
            reason="sandbox creator identity",
        )
        return self.store.activate_account(account.account_id)

    def doctor(self) -> dict[str, Any]:
        from content.store import schema_ready

        ready, missing = schema_ready(self.store.engine)
        accounts = self.store.list_accounts()
        characters = [item for account in accounts for item in self.store.list_characters(account.account_id)]
        worlds = [item for account in accounts for item in self.store.list_worlds(account.account_id)]
        series = [item for account in accounts for item in self.store.list_series(account.account_id)]
        evidence = []
        for account in accounts:
            evidence.extend(self.store.list_evidence(account_id=account.account_id))
        evidence_kinds = {item.kind for item in evidence}
        def _arch(ok: bool, **extra):
            payload = {"status": "PASS" if ok else "NOT_CONFIGURED", "lane": "ARCHITECTURE"}
            payload.update(extra)
            return payload
        def _prod(kind: str, **extra):
            payload = {"status": "PASS" if kind in evidence_kinds else "NOT_VERIFIED", "lane": "PRODUCTION_EVIDENCE", "kind": kind}
            payload.update(extra)
            return payload
        return {
            "ACCOUNT_RUNTIME": _arch(ready, count=len(accounts), missing=missing),
            "CHARACTER_RUNTIME": _arch(ready, count=len(characters)),
            "WORLD_RUNTIME": _arch(ready, count=len(worlds)),
            "SERIES_RUNTIME": _arch(ready, count=len(series)),
            "CONTINUITY_RUNTIME": _arch(ready),
            "ASSET_LINEAGE": _arch(ready),
            "PLATFORM_VARIANT": _arch(callable(differentiate_package)),
            "CREATIVE_RUNTIME": _arch(True, owner="creative.runtime.container.CreativeRuntime"),
            "ACCOUNT_CONTEXT": _arch(True, owner="content.models.AccountContext"),
            "MULTI_ACCOUNT_RUNTIME": _arch(ready),
            "EPISODE_TRANSACTION": _arch(ready),
            "PLATFORM_CHARACTER_DNA": _arch(ready),
            "PLATFORM_WORLD_DNA": _arch(ready),
            "PLATFORM_CREATIVE_DNA": _arch(ready),
            "PLATFORM_ASSET_POOL": _arch(ready),
            "PLATFORM_ASSET_ISOLATION": _arch(ready),
            "ASSET_FRESHNESS": _arch(True, owner="content.assets.AssetFreshnessGuard"),
            "EPISODE_NEW_ASSET_REQUIRED": _arch(True),
            "SAME_FILE_REUSE_BLOCK": _arch(True),
            "DERIVED_ASSET_LINEAGE": _arch(ready),
            "CROSS_PLATFORM_PRIMARY_ASSET_BLOCK": _arch(True),
            "REFERENCE_ASSET_SUPPORT": _arch(True, owner="content.assets.ReferenceAssetResolver"),
            "PROMPT_COMPILER": _arch(True, owner="content.compiler.PromptCompiler"),
            "IMAGE_PROMPT_PACKAGE": _arch(True),
            "VIDEO_PROMPT_PACKAGE": _arch(True),
            "IMAGE_TO_VIDEO_PROMPT_PACKAGE": _arch(True),
            "PROMPT_NOVELTY": _arch(True),
            "CHARACTER_CONTINUITY": _arch(True, owner="content.qa.CharacterContinuityQA"),
            "WORLD_CONTINUITY": _arch(ready),
            "PLATFORM_LEARNING_DNA": _arch(ready),
            "LEARNING_ISOLATION": _arch(ready),
            "PROMPT_PATTERN_LIBRARY": _arch(ready),
            "OBSIDIAN_EPISODE_MEMORY": _arch(True, owner="memory.brain.KnowledgeBrain"),
            "OBSIDIAN_PROMPT_MEMORY": _arch(True, owner="content.compiler.PromptCompiler"),
            "MANUAL_LECHUANG_IMPORT": _arch(True, owner="content.assets.PlatformAssetService"),
            "MEDIA_ASSET_QA": _arch(True, owner="creative.judges.technical.TechnicalQA"),
            "CONTENT_PACKAGE_ASSET_MAPPING": _arch(ready),
            "REVISION_RUNTIME": _arch(ready),
            "LINEAGE_RUNTIME": _arch(ready),
            "PUBLICATION_RUNTIME": _prod("PUBLICATION"),
            "ANALYTICS_RUNTIME": _prod("ANALYTICS_IMPORTED"),
            "PRODUCTION_RUN": _arch(ready),
            "ACCOUNT_OS": _arch(ready, owner="content.models.AccountProfile"),
            "TASK_OS": _arch(ready, owner="content.tasks.TaskOS"),
            "CONTENT_CALENDAR": _arch(ready, owner="content.planner.EpisodePlanner"),
            "CONTENT_PLANNER": _arch(True, owner="content.planner.EpisodePlanner"),
            "EPISODE_PLANNER": _arch(True, owner="content.planner.EpisodePlanner"),
            "CREATOR_IDENTITY": _arch(ready, owner="content.models.CreatorAccount"),
            "CREATOR_STATE": _arch(ready, owner="content.models.CreatorState"),
            "CREATOR_STRATEGY": _arch(ready, owner="content.planner.CreatorStrategyService"),
            "CONTENT_PORTFOLIO": _arch(ready, owner="content.planner.ContentNoveltyService"),
            "CONTENT_NOVELTY": _arch(True, owner="content.planner.ContentNoveltyService"),
            "SERIES_ENGINE": _arch(ready, owner="content.models.ContentSeries"),
            "DECISION_TRACE": _arch(True, owner="content.planner.CreatorBrain"),
            "PRODUCTION_MEMORY": _arch(ready, owner="content.planner.ProductionMemoryService"),
            "PACKAGE": _arch(ready, owner="content.models.ContentPackage"),
            "HANDOFF": _arch(True, note="XHS is HANDOFF_ONLY"),
            "MANUAL_LECHUANG": _arch(True, owner="content.assets.PlatformAssetService"),
            "SYSTEM_CAPABILITY": _arch(ready),
            "ACCOUNT_CONFIGURATION": {"status": "PASS" if accounts else "NOT_CONFIGURED", "lane": "CONFIGURATION"},
            "CORE_PRODUCTION": {
                "status": self.production_readiness(persist=False).get("CORE_PRODUCTION") if ready else "NOT_CONFIGURED",
                "lane": "ARCHITECTURE",
            },
            "CORE_CONTENT_PRODUCTION": {
                "status": self.production_readiness(persist=False).get("CORE_PRODUCTION") if ready else "NOT_CONFIGURED",
                "lane": "ARCHITECTURE",
                "note": "OAuth/PlatformConnection never required",
            },
            "POST_PRODUCTION": _prod("ANALYTICS_IMPORTED"),
            "FULL_LOOP": {"status": "NOT_VERIFIED", "lane": "PRODUCTION_EVIDENCE"},
            "LEARNING_RUNTIME": _prod("LEARNING_WRITTEN"),
            "PRODUCTION_EVIDENCE": {
                "status": "NOT_VERIFIED" if not evidence else (
                    "PASS" if ("XHS_HANDOFF" in evidence_kinds or "HANDOFF" in evidence_kinds) and any(
                        kind.endswith("REAL_ASSET_IMPORTED") for kind in evidence_kinds
                    ) else "NOT_VERIFIED"
                ),
                "lane": "PRODUCTION_EVIDENCE",
                "count": len(evidence),
            },
            "REAL_DAY_1": _prod("DAY_001_REAL_ASSET_IMPORTED"),
            "REAL_DAY_2": _prod("DAY_002_REAL_ASSET_IMPORTED"),
            "REAL_DAY_3": _prod("DAY_003_REAL_ASSET_IMPORTED"),
        }

    def packages_for_request(self, text: str) -> list[dict[str, Any]]:
        return [self.prepare_target(target, text=text) for target in self.resolver.resolve_many(text)]


def _text_or(field: Any, fallback: str = "") -> str:
    if isinstance(field, KnowledgeField):
        value = "" if not field.known() else str(field.value or "")
        return value or fallback
    return str(field or fallback) or fallback


def _xhs_character(account_id: str) -> VirtualCharacter:
    return VirtualCharacter(
        character_id=f"{account_id}-character",
        account_id=account_id,
        name="张满血",
        gender="female",
        age_range="26-28",
        appearance_profile={"presence": "calm Shenzhen operator, not a model"},
        body_profile={"type": "athletic-slim", "posture": "upright after training"},
        face_profile={"shape": "oval", "expression": "quiet focus"},
        hair_profile={"length": "shoulder", "color": "natural black", "style": "low ponytail or loose after gym"},
        skin_profile={"tone": "warm light", "texture": "real pores, slight post-workout flush"},
        clothing_profile={"day": "linen shirt and trousers", "gym": "black tank and shorts", "coffee": "oversized white shirt"},
        personality_profile={"energy": "steady", "values": "真实、克制、把生活过清楚"},
        accessories=("simple silver hoop earrings", "black sports watch"),
        location="深圳",
        occupation="independent operator",
        values=("真实", "克制", "把生活过清楚"),
        behavior="moves through the day without posing for the camera",
        platform_personality="peer sharing a real day",
        content_behavior="candid smartphone stills of training, coffee, and Shenzhen streets",
        audience_relationship="peer sharing a real day",
        forbidden_changes=("beauty filter", "plastic skin", "unexplained haircut", "studio cyclorama"),
        character_dna={"camera": "eye-level handheld phone", "authenticity": "real skin, real sweat, imperfect frame"},
    )


def _douyin_character(account_id: str) -> VirtualCharacter:
    return VirtualCharacter(
        character_id=f"{account_id}-character",
        account_id=account_id,
        name="训练角色",
        gender="female",
        age_range="24-28",
        appearance_profile={"presence": "high-energy trainer in motion"},
        body_profile={"type": "athletic", "posture": "ready to move"},
        face_profile={"shape": "oval", "expression": "drive"},
        hair_profile={"length": "tied back", "color": "natural black"},
        skin_profile={"tone": "warm", "texture": "sweat and motion, no filter"},
        clothing_profile={"training": "fitted black set", "street": "hoodie and shorts"},
        personality_profile={"energy": "high", "values": "把训练做完"},
        accessories=("black sports watch",),
        location="深圳训练馆",
        occupation="trainer-operator",
        values=("把训练做完",),
        behavior="starts already in action",
        platform_personality="coach in motion",
        content_behavior="first-three-seconds vertical training clips",
        audience_relationship="coach in motion",
        forbidden_changes=("static slideshow", "reused still as video"),
        character_dna={"camera": "push-in handheld", "authenticity": "real sweat and motion"},
    )


def _xhs_world(account_id: str) -> AccountWorld:
    return AccountWorld(
        world_id=f"{account_id}-world",
        account_id=account_id,
        name="深圳认真生活",
        world_description="A long-running Shenzhen life: apartment, gym, neighborhood coffee, outdoor walks.",
        core_theme="把认真生活拍成连续日记",
        city="深圳",
        season="late summer into autumn",
        time_of_day="morning to golden hour",
        lighting="soft daylight through windows and street shade",
        lifestyle="train, coffee, walk, write",
        locations=("南山公寓", "小区健身房", "街角咖啡店", "深圳户外步道"),
        daily_life_rules=("keep the same apartment and gym", "weather can change, city cannot"),
        story_rules=("each episode is a new day beat", "never republish yesterday's still"),
        visual_language={"light": "soft daylight", "city": "深圳", "season": "late summer"},
        taboos=("luxury catalog", "beauty filter", "identical pose reuse"),
        audience="people who want a calmer operator life",
        world_dna={"spaces": "apartment / gym / coffee / outdoor", "continuity": "same city, new beat"},
    )


def _douyin_world(account_id: str) -> AccountWorld:
    return AccountWorld(
        world_id=f"{account_id}-world",
        account_id=account_id,
        name="高能量训练",
        world_description="A Shenzhen training hall and outdoor sprint loop built for vertical motion.",
        core_theme="训练挑战",
        city="深圳",
        season="training season",
        time_of_day="early session",
        lighting="hard gym light and outdoor contrast",
        lifestyle="train, recover, film the next set",
        locations=("训练馆", "户外跑道"),
        daily_life_rules=("start in motion", "do not freeze yesterday's still"),
        visual_language={"light": "punchy contrast", "city": "深圳"},
        taboos=("static slideshow", "reused still as video"),
        audience="people who want a harder training day",
        world_dna={"spaces": "gym / track", "continuity": "same training world, new action"},
    )
