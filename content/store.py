"""PostgreSQL is the source of truth for account worlds, series, and continuity."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from content.models import (
    ACCOUNT_PLATFORMS,
    AccountOperatingState,
    AccountProfile,
    AccountWorld,
    AnalyticsRecord,
    AssetLineage,
    AssetReferenceSnapshot,
    CharacterRevision,
    ContentCalendarEntry,
    ContentPackage,
    ContentPackageAsset,
    ContentRevision,
    ContentSeries,
    ContinuityMemory,
    CreativeContext,
    CreativeExecutionReceipt,
    CreatorTask,
    Episode,
    EpisodeConflict,
    ExistingAssetError,
    IsolationError,
    KnowledgeField,
    LearningRecord,
    LifecycleTransition,
    ManualOverride,
    PatternPromotion,
    PerformanceFeedback,
    PlatformAccount,
    PlatformAssetPool,
    PlatformCreativeDNA,
    PlatformLearningProfile,
    ProductionEvidence,
    ProductionReadinessRecord,
    ProductionRun,
    PromptPackage,
    PromptPattern,
    VirtualCharacter,
    WorldRevision,
    utcnow,
)


CONTINUITY_TABLE_NAMES = (
    "platform_accounts",
    "virtual_characters",
    "account_worlds",
    "content_series",
    "episodes",
    "creative_contexts",
    "content_revisions",
    "account_memories",
    "character_memories",
    "world_memories",
    "series_memories",
    "episode_memories",
    "performance_feedback",
    "asset_lineage",
    "account_selections",
    "knowledge_documents",
    "platform_asset_pools",
    "platform_creative_dna",
    "prompt_packages",
    "prompt_patterns",
    "platform_learning_profiles",
    "content_package_assets",
    "media_assets",
    "content_packages",
    "production_runs",
    "production_evidence",
    "analytics_records",
    "learning_records",
    "creative_execution_receipts",
    "character_revisions",
    "world_revisions",
    "asset_reference_snapshots",
    "pattern_promotions",
    "lifecycle_transitions",
    "account_profiles",
    "account_operating_states",
    "manual_overrides",
    "creator_tasks",
    "content_calendar",
    "production_readiness_records",
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _parse_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed


def _json(value: Any, default: Any) -> Any:
    return default if value is None else value


def _tuple(value: Any) -> tuple:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    return tuple(value)


def is_test_runtime() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or os.environ.get("MEITI_CONTINUITY_STORE") == "memory"


def sqlite_engine(url: str | None = None):
    connect_args = {"check_same_thread": False}
    if url and url != "sqlite://":
        return create_engine(url, connect_args=connect_args)
    return create_engine("sqlite://", connect_args=connect_args, poolclass=StaticPool)


def production_engine():
    from scripts.db.engine import engine
    return engine


def schema_ready(engine) -> tuple[bool, list[str]]:
    from sqlalchemy import inspect

    existing = set(inspect(engine).get_table_names())
    missing = [name for name in CONTINUITY_TABLE_NAMES if name not in existing]
    return (not missing, missing)


def ensure_continuity_schema(engine, *, allow_create: bool = False) -> None:
    from scripts.db.models import Base

    ready, missing = schema_ready(engine)
    if ready:
        return
    if not allow_create:
        from creative.errors import SchemaNotReady
        raise SchemaNotReady("continuity schema missing: " + ", ".join(missing))
    tables = [Base.metadata.tables[name] for name in CONTINUITY_TABLE_NAMES if name in Base.metadata.tables]
    Base.metadata.create_all(engine, tables=tables)


class ContinuityStore:
    """Unique persistence owner for account worlds, series, episodes, and lineage."""

    def __init__(self, *, engine=None) -> None:
        if engine is None:
            engine = sqlite_engine() if is_test_runtime() else production_engine()
        self.engine = engine
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        dialect = getattr(getattr(self.engine, "dialect", None), "name", "")
        allow_create = is_test_runtime() or dialect == "sqlite"
        ensure_continuity_schema(self.engine, allow_create=allow_create)

    @classmethod
    def testing(cls) -> "ContinuityStore":
        return cls(engine=sqlite_engine())

    @classmethod
    def production(cls) -> "ContinuityStore":
        store = cls.__new__(cls)
        store.engine = production_engine()
        store.Session = sessionmaker(autocommit=False, autoflush=False, bind=store.engine)
        ensure_continuity_schema(store.engine, allow_create=False)
        return store

    def _session(self):
        return self.Session()

    def _upsert(self, model, key: str, value: str, fields: dict[str, Any]) -> None:
        with self._session() as session:
            row = session.get(model, value)
            if row is None:
                session.add(model(**{key: value}, **fields))
            else:
                for name, item in fields.items():
                    setattr(row, name, item)
            session.commit()

    def save_account(self, account: PlatformAccount) -> PlatformAccount:
        from scripts.db.models import PlatformAccountRecord

        if account.platform not in ACCOUNT_PLATFORMS:
            raise ValueError(f"unsupported platform: {account.platform}")
        self._upsert(PlatformAccountRecord, "account_id", account.account_id, {
            "platform": account.platform,
            "external_account_id": account.external_account_id,
            "display_name": account.display_name,
            "status": account.status,
            "credential_ref": account.credential_ref,
            "character_id": account.character_id,
            "world_id": account.world_id,
            "series_id": account.series_id,
            "default_style_profile_id": account.default_style_profile_id,
            "social_account_id": account.social_account_id,
            "activated_at": _parse_dt(account.activated_at),
            "updated_at": _now(),
        })
        return account

    def get_account(self, account_id: str) -> PlatformAccount | None:
        from scripts.db.models import PlatformAccountRecord

        with self._session() as session:
            row = session.get(PlatformAccountRecord, account_id)
            return _account_from_row(row) if row else None

    def list_accounts(self, *, platform: str | None = None) -> list[PlatformAccount]:
        from scripts.db.models import PlatformAccountRecord

        with self._session() as session:
            stmt = select(PlatformAccountRecord)
            if platform:
                stmt = stmt.where(PlatformAccountRecord.platform == platform)
            rows = list(session.execute(stmt).scalars())
        accounts = [_account_from_row(row) for row in rows]
        accounts.sort(key=lambda item: (item.platform, item.display_name or item.account_id))
        return accounts

    def active_account(self, *, platform: str | None = None) -> PlatformAccount | None:
        selected = self.current_account(platform=platform)
        if selected is not None:
            return selected
        accounts = [item for item in self.list_accounts(platform=platform) if item.status == "ACTIVE"]
        if not accounts:
            return None
        if len(accounts) > 1:
            return None
        return accounts[0]

    def current_account(self, *, platform: str | None = None) -> PlatformAccount | None:
        from scripts.db.models import AccountSelectionRecord

        key = f"platform:{platform}" if platform else "global"
        with self._session() as session:
            row = session.get(AccountSelectionRecord, key)
            if row is None and platform:
                row = session.get(AccountSelectionRecord, "global")
            if row is None:
                return None
            account = self.get_account(row.account_id)
        if account is None:
            return None
        if platform and account.platform != platform:
            return None
        return account

    def select_current_account(self, account_id: str, *, reason: str = "explicit") -> PlatformAccount:
        from scripts.db.models import AccountSelectionRecord

        account = self.get_account(account_id)
        if account is None:
            raise KeyError(account_id)
        now = _now()
        with self._session() as session:
            for key in (f"platform:{account.platform}", "global"):
                row = session.get(AccountSelectionRecord, key)
                fields = {"account_id": account.account_id, "platform": account.platform, "reason": reason, "updated_at": now}
                if row is None:
                    session.add(AccountSelectionRecord(selection_key=key, **fields))
                else:
                    for name, value in fields.items():
                        setattr(row, name, value)
            session.commit()
        return account

    def activate_account(self, account_id: str) -> PlatformAccount:
        account = self.get_account(account_id)
        if account is None:
            raise KeyError(account_id)
        now = utcnow()
        updated = PlatformAccount(**{**account.__dict__, "status": "ACTIVE", "activated_at": now, "updated_at": now})
        saved = self.save_account(updated)
        self.select_current_account(saved.account_id, reason="activate")
        return saved

    def save_character(self, character: VirtualCharacter) -> VirtualCharacter:
        from scripts.db.models import VirtualCharacterRecord

        self._require_account(character.account_id)
        self._upsert(VirtualCharacterRecord, "character_id", character.character_id, {
            "account_id": character.account_id,
            "name": character.name,
            "gender": character.gender,
            "age_range": character.age_range,
            "appearance_profile": dict(character.appearance_profile),
            "body_profile": dict(character.body_profile),
            "face_profile": dict(character.face_profile),
            "hair_profile": dict(character.hair_profile),
            "skin_profile": dict(character.skin_profile),
            "clothing_profile": dict(character.clothing_profile),
            "personality_profile": dict(character.personality_profile),
            "background_story": character.background_story,
            "speaking_style": character.speaking_style,
            "behavioral_traits": list(character.behavioral_traits),
            "visual_identity_rules": dict(character.visual_identity_rules),
            "forbidden_changes": list(character.forbidden_changes),
            "reference_asset_ids": list(character.reference_asset_ids),
            "derived_from_character_id": character.derived_from_character_id,
            "occupation": character.occupation,
            "location": character.location,
            "values": list(character.values),
            "behavior": character.behavior,
            "speech": character.speech,
            "style": dict(character.style),
            "accessories": list(character.accessories),
            "photography": character.photography,
            "lighting": character.lighting,
            "platform_personality": character.platform_personality,
            "content_behavior": character.content_behavior,
            "audience_relationship": character.audience_relationship,
            "continuity_rules": dict(character.continuity_rules),
            "character_dna": dict(character.character_dna),
            "status": character.status,
            "version": character.version,
            "updated_at": _now(),
        })
        return character

    def get_character(self, character_id: str, *, account_id: str | None = None, allow_share: bool = False) -> VirtualCharacter | None:
        from scripts.db.models import VirtualCharacterRecord

        with self._session() as session:
            row = session.get(VirtualCharacterRecord, character_id)
            if row is None:
                return None
            character = _character_from_row(row)
        if account_id and character.account_id != account_id and not allow_share:
            raise IsolationError(f"{account_id} cannot read character {character_id} owned by {character.account_id}")
        return character

    def list_characters(self, account_id: str) -> list[VirtualCharacter]:
        from scripts.db.models import VirtualCharacterRecord

        with self._session() as session:
            rows = session.execute(select(VirtualCharacterRecord).where(VirtualCharacterRecord.account_id == account_id)).scalars()
            return [_character_from_row(row) for row in rows]

    def save_world(self, world: AccountWorld) -> AccountWorld:
        from scripts.db.models import AccountWorldRecord

        self._require_account(world.account_id)
        self._upsert(AccountWorldRecord, "world_id", world.world_id, {
            "account_id": world.account_id,
            "name": world.name,
            "world_description": world.world_description,
            "core_theme": world.core_theme,
            "values": list(world.values),
            "tone": world.tone,
            "visual_language": dict(world.visual_language),
            "locations": list(world.locations),
            "daily_life_rules": list(world.daily_life_rules),
            "story_rules": list(world.story_rules),
            "audience": world.audience,
            "taboos": list(world.taboos),
            "brand_rules": list(world.brand_rules),
            "city": world.city,
            "season": world.season,
            "time_of_day": world.time_of_day,
            "lighting": world.lighting,
            "lifestyle": world.lifestyle,
            "social_relations": list(world.social_relations),
            "world_dna": dict(world.world_dna),
            "status": world.status,
            "version": world.version,
            "updated_at": _now(),
        })
        return world

    def get_world(self, world_id: str, *, account_id: str | None = None, allow_share: bool = False) -> AccountWorld | None:
        from scripts.db.models import AccountWorldRecord

        with self._session() as session:
            row = session.get(AccountWorldRecord, world_id)
            if row is None:
                return None
            world = _world_from_row(row)
        if account_id and world.account_id != account_id and not allow_share:
            raise IsolationError(f"{account_id} cannot read world {world_id} owned by {world.account_id}")
        return world

    def list_worlds(self, account_id: str) -> list[AccountWorld]:
        from scripts.db.models import AccountWorldRecord

        with self._session() as session:
            rows = session.execute(select(AccountWorldRecord).where(AccountWorldRecord.account_id == account_id)).scalars()
            return [_world_from_row(row) for row in rows]

    def save_series(self, series: ContentSeries) -> ContentSeries:
        from scripts.db.models import ContentSeriesRecord

        self._require_account(series.account_id)
        if series.world_id:
            world = self.get_world(series.world_id, account_id=series.account_id)
            if world is None:
                raise IsolationError(f"world {series.world_id} is not owned by {series.account_id}")
        self._upsert(ContentSeriesRecord, "series_id", series.series_id, {
            "account_id": series.account_id,
            "world_id": series.world_id,
            "name": series.name,
            "description": series.description,
            "series_type": series.series_type,
            "content_rules": dict(series.content_rules),
            "continuity_rules": dict(series.continuity_rules),
            "status": series.status,
            "start_date": series.start_date,
            "end_date": series.end_date,
            "current_episode_no": series.current_episode_no,
            "updated_at": _now(),
        })
        return series

    def get_series(self, series_id: str, *, account_id: str | None = None, allow_share: bool = False) -> ContentSeries | None:
        from scripts.db.models import ContentSeriesRecord

        with self._session() as session:
            row = session.get(ContentSeriesRecord, series_id)
            if row is None:
                return None
            series = _series_from_row(row)
        if account_id and series.account_id != account_id and not allow_share:
            raise IsolationError(f"{account_id} cannot read series {series_id} owned by {series.account_id}")
        return series

    def list_series(self, account_id: str) -> list[ContentSeries]:
        from scripts.db.models import ContentSeriesRecord

        with self._session() as session:
            rows = session.execute(select(ContentSeriesRecord).where(ContentSeriesRecord.account_id == account_id)).scalars()
            return [_series_from_row(row) for row in rows]

    def active_series(self, account_id: str) -> ContentSeries | None:
        series = [item for item in self.list_series(account_id) if item.status == "ACTIVE"]
        if not series:
            return None
        series.sort(key=lambda item: item.updated_at or "", reverse=True)
        return series[0]

    def save_episode(self, episode: Episode) -> Episode:
        from scripts.db.models import EpisodeRecord

        series = self.get_series(episode.series_id)
        if series is None:
            raise KeyError(episode.series_id)
        if episode.account_id and episode.account_id != series.account_id:
            raise IsolationError(f"episode {episode.episode_id} account does not match series {series.series_id}")
        if not episode.account_id:
            episode = Episode(**{**episode.__dict__, "account_id": series.account_id})
        self._upsert(EpisodeRecord, "episode_id", episode.episode_id, {
            "series_id": episode.series_id,
            "account_id": episode.account_id,
            "episode_no": episode.episode_no,
            "title": episode.title,
            "brief": episode.brief,
            "previous_episode_id": episode.previous_episode_id,
            "next_episode_id": episode.next_episode_id,
            "continuity_context": dict(episode.continuity_context),
            "character_state": dict(episode.character_state),
            "world_state": dict(episode.world_state),
            "location_state": dict(episode.location_state),
            "visual_state": dict(episode.visual_state),
            "story_state": dict(episode.story_state),
            "content_status": episode.content_status,
            "campaign_id": episode.campaign_id,
            "content_package_id": episode.content_package_id,
            "primary_asset_id": episode.primary_asset_id,
            "prompt_id": episode.prompt_id,
            "character_revision": episode.character_revision,
            "world_revision": episode.world_revision,
            "production_run_id": episode.production_run_id,
            "updated_at": _now(),
        })
        return episode

    def get_episode(self, episode_id: str, *, account_id: str | None = None, allow_share: bool = False) -> Episode | None:
        from scripts.db.models import EpisodeRecord

        with self._session() as session:
            row = session.get(EpisodeRecord, episode_id)
            if row is None:
                return None
            episode = _episode_from_row(row)
        if account_id and episode.account_id != account_id and not allow_share:
            raise IsolationError(f"{account_id} cannot read episode {episode_id} owned by {episode.account_id}")
        return episode

    def list_episodes(self, series_id: str) -> list[Episode]:
        from scripts.db.models import EpisodeRecord

        with self._session() as session:
            rows = session.execute(select(EpisodeRecord).where(EpisodeRecord.series_id == series_id)).scalars()
            items = [_episode_from_row(row) for row in rows]
        items.sort(key=lambda item: item.episode_no)
        return items

    def latest_episode(self, series_id: str) -> Episode | None:
        episodes = self.list_episodes(series_id)
        return episodes[-1] if episodes else None

    def save_context(self, context: CreativeContext) -> CreativeContext:
        from scripts.db.models import CreativeContextRecord

        self._require_account(context.account_id)
        self._upsert(CreativeContextRecord, "context_id", context.context_id, {
            "account_id": context.account_id,
            "platform": context.platform,
            "character_id": context.character_id,
            "world_id": context.world_id,
            "series_id": context.series_id,
            "episode_id": context.episode_id,
            "campaign_id": context.campaign_id,
            "user_request": context.user_request,
            "creative_request": context.creative_request,
            "normalized_prompt": context.normalized_prompt,
            "system_constraints": dict(context.system_constraints),
            "character_context": dict(context.character_context),
            "world_context": dict(context.world_context),
            "continuity_context": dict(context.continuity_context),
            "platform_context": dict(context.platform_context),
            "generation_parameters": dict(context.generation_parameters),
            "provider": context.provider,
            "model": context.model,
            "provider_task_id": context.provider_task_id,
            "resolved_target": dict(context.resolved_target),
        })
        return context

    def get_context(self, context_id: str) -> CreativeContext | None:
        from scripts.db.models import CreativeContextRecord

        with self._session() as session:
            row = session.get(CreativeContextRecord, context_id)
            return _context_from_row(row) if row else None

    def save_revision(self, revision: ContentRevision) -> ContentRevision:
        from scripts.db.models import ContentRevisionRecord

        self._upsert(ContentRevisionRecord, "revision_id", revision.revision_id, {
            "content_package_id": revision.content_package_id,
            "version": revision.version,
            "parent_revision_id": revision.parent_revision_id,
            "change_summary": revision.change_summary,
            "snapshot": dict(revision.snapshot),
            "created_by": revision.created_by,
        })
        return revision

    def list_revisions(self, content_package_id: str) -> list[ContentRevision]:
        from scripts.db.models import ContentRevisionRecord

        with self._session() as session:
            rows = session.execute(
                select(ContentRevisionRecord).where(ContentRevisionRecord.content_package_id == content_package_id)
            ).scalars()
            items = [_revision_from_row(row) for row in rows]
        items.sort(key=lambda item: item.version)
        return items

    def save_memory(self, memory: ContinuityMemory) -> ContinuityMemory:
        if memory.kind == "performance":
            raise ValueError("use save_feedback for performance memory")
        self._require_account(memory.account_id)
        model = _memory_model(memory.kind)
        fields = {
            "kind": memory.kind,
            "account_id": memory.account_id,
            "subject_id": memory.subject_id,
            "key": memory.key,
            "value": memory.value,
            "source": memory.source,
            "namespace": model.__tablename__,
        }
        self._upsert(model, "memory_id", memory.memory_id, fields)
        return memory

    def list_memories(self, *, account_id: str, kind: str | None = None, subject_id: str | None = None) -> list[ContinuityMemory]:
        kinds = (kind,) if kind else ("account", "character", "world", "series", "episode")
        items: list[ContinuityMemory] = []
        with self._session() as session:
            for item_kind in kinds:
                model = _memory_model(item_kind)
                stmt = select(model).where(model.account_id == account_id)
                if subject_id:
                    stmt = stmt.where(model.subject_id == subject_id)
                items.extend(_memory_from_row(row) for row in session.execute(stmt).scalars())
        return items

    def save_feedback(self, feedback: PerformanceFeedback) -> PerformanceFeedback:
        from scripts.db.models import PerformanceFeedbackRecord

        self._require_account(feedback.account_id)
        self._upsert(PerformanceFeedbackRecord, "feedback_id", feedback.feedback_id, {
            "account_id": feedback.account_id,
            "platform": feedback.platform,
            "content_package_id": feedback.content_package_id,
            "episode_id": feedback.episode_id,
            "topic": feedback.topic,
            "hook": feedback.hook,
            "visual_style": feedback.visual_style,
            "caption_style": feedback.caption_style,
            "duration": feedback.duration,
            "scene": feedback.scene,
            "action": feedback.action,
            "audio": feedback.audio,
            "engagement": dict(feedback.engagement),
            "retention": dict(feedback.retention),
            "publication_id": feedback.publication_id,
        })
        return feedback

    def list_feedback(self, account_id: str) -> list[PerformanceFeedback]:
        from scripts.db.models import PerformanceFeedbackRecord

        with self._session() as session:
            rows = session.execute(select(PerformanceFeedbackRecord).where(PerformanceFeedbackRecord.account_id == account_id)).scalars()
            return [_feedback_from_row(row) for row in rows]

    def save_lineage(self, lineage: AssetLineage) -> AssetLineage:
        from scripts.db.models import AssetLineageRecord

        self._require_account(lineage.account_id)
        self._upsert(AssetLineageRecord, "lineage_id", lineage.lineage_id, {
            "asset_id": lineage.asset_id,
            "account_id": lineage.account_id,
            "series_id": lineage.series_id,
            "episode_id": lineage.episode_id,
            "content_package_id": lineage.content_package_id,
            "creative_context_id": lineage.creative_context_id,
            "character_id": lineage.character_id,
            "world_id": lineage.world_id,
            "user_request": lineage.user_request,
            "generation_request": dict(lineage.generation_request),
            "provider": lineage.provider,
            "provider_task_id": lineage.provider_task_id,
            "model": lineage.model,
            "attempt_no": lineage.attempt_no,
            "parent_asset_id": lineage.parent_asset_id or "",
            "qa_decision": lineage.qa_decision,
            "published": bool(lineage.published),
            "selected_for_package": bool(lineage.selected_for_package),
            "source_asset_id": lineage.source_asset_id,
            "workflow_id": lineage.workflow_id,
            "reference_asset_ids": list(lineage.reference_asset_ids),
            "origin_episode_id": lineage.origin_episode_id,
            "target_episode_id": lineage.target_episode_id,
            "origin_platform": lineage.origin_platform,
            "target_platform": lineage.target_platform,
            "reuse_mode": lineage.reuse_mode,
            "generation_mode": lineage.generation_mode,
            "tool": lineage.tool,
            "prompt_id": lineage.prompt_id,
        })
        return lineage

    def get_lineage(self, asset_id: str, *, account_id: str | None = None, allow_share: bool = False) -> AssetLineage | None:
        from scripts.db.models import AssetLineageRecord

        with self._session() as session:
            rows = list(session.execute(select(AssetLineageRecord).where(AssetLineageRecord.asset_id == asset_id)).scalars())
            if not rows:
                return None
            rows.sort(key=lambda item: int(item.attempt_no or 1))
            lineage = _lineage_from_row(rows[-1])
        if account_id and lineage.account_id != account_id and not allow_share:
            raise IsolationError(f"{account_id} cannot read asset {asset_id} owned by {lineage.account_id}")
        return lineage

    def list_lineage(self, *, account_id: str, episode_id: str | None = None) -> list[AssetLineage]:
        from scripts.db.models import AssetLineageRecord

        with self._session() as session:
            stmt = select(AssetLineageRecord).where(AssetLineageRecord.account_id == account_id)
            if episode_id:
                stmt = stmt.where(AssetLineageRecord.episode_id == episode_id)
            return [_lineage_from_row(row) for row in session.execute(stmt).scalars()]

    def next_attempt(self, *, account_id: str, episode_id: str | None, parent_asset_id: str | None) -> int:
        from scripts.db.models import AssetLineageRecord

        parent = parent_asset_id or ""
        with self._session() as session:
            stmt = select(AssetLineageRecord.attempt_no).where(
                AssetLineageRecord.account_id == account_id,
                AssetLineageRecord.episode_id == episode_id,
            )
            values = [int(item or 0) for item in session.execute(stmt).scalars()]
            return max(values, default=0) + 1

    def allocate_attempt(self, *, account_id: str, episode_id: str | None, parent_asset_id: str | None, lineage: AssetLineage) -> AssetLineage:
        from scripts.db.models import AssetLineageRecord

        parent = parent_asset_id or ""
        last_error = None
        for _ in range(8):
            attempt = self.next_attempt(account_id=account_id, episode_id=episode_id, parent_asset_id=parent)
            candidate = AssetLineage(**{**lineage.__dict__, "attempt_no": attempt, "parent_asset_id": parent or None})
            try:
                return self.save_lineage(candidate)
            except IntegrityError as exc:
                last_error = exc
                continue
        raise EpisodeConflict("concurrent attempt allocation conflict") from last_error

    def create_next_episode_tx(self, episode: Episode, *, previous: Episode | None, series: ContentSeries) -> Episode:
        from scripts.db.models import ContentSeriesRecord, EpisodeRecord

        now = _now()
        with self._session() as session:
            series_row = session.get(ContentSeriesRecord, series.series_id)
            if series_row is None:
                raise IsolationError(f"series {series.series_id} is missing")
            dialect = getattr(getattr(session.get_bind(), "dialect", None), "name", "")
            if dialect == "postgresql":
                session.execute(text("SELECT series_id FROM content_series WHERE series_id = :sid FOR UPDATE"), {"sid": series.series_id})
            previous_row = session.get(EpisodeRecord, previous.episode_id) if previous else None
            expected_no = int(series_row.current_episode_no or 0) + 1
            if previous_row is not None:
                expected_no = int(previous_row.episode_no) + 1
            if episode.episode_no != expected_no:
                raise EpisodeConflict(f"episode {expected_no} already exists for series {series.series_id}")
            existing = session.execute(
                select(EpisodeRecord).where(
                    EpisodeRecord.series_id == series.series_id,
                    EpisodeRecord.episode_no == episode.episode_no,
                )
            ).scalar_one_or_none()
            if existing is not None:
                raise EpisodeConflict(f"episode {episode.episode_no} already exists for series {series.series_id}")
            session.add(EpisodeRecord(
                episode_id=episode.episode_id,
                series_id=episode.series_id,
                account_id=episode.account_id,
                episode_no=episode.episode_no,
                title=episode.title,
                brief=episode.brief,
                previous_episode_id=episode.previous_episode_id,
                next_episode_id=episode.next_episode_id,
                continuity_context=dict(episode.continuity_context),
                character_state=dict(episode.character_state),
                world_state=dict(episode.world_state),
                location_state=dict(episode.location_state),
                visual_state=dict(episode.visual_state),
                story_state=dict(episode.story_state),
                content_status=episode.content_status,
                campaign_id=episode.campaign_id,
                content_package_id=episode.content_package_id,
                primary_asset_id=episode.primary_asset_id,
                prompt_id=episode.prompt_id,
                character_revision=episode.character_revision,
                world_revision=episode.world_revision,
                production_run_id=episode.production_run_id,
                created_at=now,
                updated_at=now,
            ))
            if previous_row is not None:
                previous_row.next_episode_id = episode.episode_id
                previous_row.updated_at = now
            series_row.current_episode_no = episode.episode_no
            series_row.updated_at = now
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise EpisodeConflict(f"episode {episode.episode_no} already exists for series {series.series_id}") from exc
        return episode

    def save_package(self, package: ContentPackage) -> ContentPackage:
        from scripts.db.models import ContentPackageRecord
        from sqlalchemy import inspect as sa_inspect

        if "content_packages" not in sa_inspect(self.engine).get_table_names():
            return package
        self._upsert(ContentPackageRecord, "package_id", package.package_id, {
            "brand_id": package.brand_id,
            "creator_id": package.creator_id,
            "campaign_id": package.campaign_id,
            "topic": package.topic,
            "content_pillar": package.content_pillar,
            "hook": package.hook,
            "format": package.format,
            "audience": package.audience,
            "title": package.title,
            "caption": package.caption,
            "body": package.body,
            "evidence_ids": list(package.evidence_ids),
            "media_assets": list(package.media_assets),
            "commerce_intent": package.commerce_intent,
            "variants": list(package.variants),
            "metadata_json": dict(package.metadata or {}),
            "account_id": package.account_id,
            "series_id": package.series_id,
            "episode_id": package.episode_id,
            "platform": package.platform or "",
            "status": package.status,
            "character_id": package.character_id,
            "world_id": package.world_id,
            "creative_context_id": package.creative_context_id,
            "revision": package.revision,
            "current_revision": package.current_revision,
            "reference_assets": list(package.reference_assets),
            "primary_assets": list(package.primary_assets),
            "published_assets": list(package.published_assets),
            "prompt_id": package.prompt_id,
            "updated_at": _now(),
        })
        return package

    def save_package_snapshot(self, package: ContentPackage, *, change_summary: str, created_by: str = "meiti") -> ContentRevision:
        revisions = self.list_revisions(package.package_id)
        version = (revisions[-1].version + 1) if revisions else package.revision
        parent = revisions[-1].revision_id if revisions else None
        snapshot = {
            "package_id": package.package_id,
            "title": package.title,
            "body": package.body,
            "caption": package.caption,
            "hook": package.hook,
            "media_assets": list(package.media_assets),
            "status": package.status,
            "platform": package.platform,
            "account_id": package.account_id,
            "series_id": package.series_id,
            "episode_id": package.episode_id,
            "metadata": dict(package.metadata or {}),
        }
        revision = self.save_revision(ContentRevision(
            revision_id=uuid4().hex,
            content_package_id=package.package_id,
            version=version,
            parent_revision_id=parent,
            change_summary=change_summary,
            snapshot=snapshot,
            created_by=created_by,
        ))
        self.save_package(ContentPackage(**{**package.__dict__, "revision": version, "current_revision": revision.revision_id}))
        return revision

    def delete_episode(self, episode_id: str) -> None:
        from scripts.db.models import EpisodeRecord

        with self._session() as session:
            row = session.get(EpisodeRecord, episode_id)
            if row is not None:
                session.delete(row)
                session.commit()

    def save_pool(self, pool: PlatformAssetPool) -> PlatformAssetPool:
        from scripts.db.models import PlatformAssetPoolRecord

        self._require_account(pool.account_id)
        self._upsert(PlatformAssetPoolRecord, "pool_id", pool.pool_id, {
            "account_id": pool.account_id,
            "platform": pool.platform,
            "character_id": pool.character_id,
            "world_id": pool.world_id,
        })
        return pool

    def get_pool(self, *, account_id: str, platform: str) -> PlatformAssetPool | None:
        from scripts.db.models import PlatformAssetPoolRecord

        with self._session() as session:
            row = session.execute(
                select(PlatformAssetPoolRecord).where(
                    PlatformAssetPoolRecord.account_id == account_id,
                    PlatformAssetPoolRecord.platform == platform,
                )
            ).scalar_one_or_none()
            return _pool_from_row(row) if row else None

    def save_creative_dna(self, dna: PlatformCreativeDNA) -> PlatformCreativeDNA:
        from scripts.db.models import PlatformCreativeDNARecord

        self._require_account(dna.account_id)
        self._upsert(PlatformCreativeDNARecord, "dna_id", dna.dna_id, {
            "account_id": dna.account_id,
            "platform": dna.platform,
            "visual_style": dict(dna.visual_style),
            "copy_style": dict(dna.copy_style),
            "hook_style": dna.hook_style,
            "camera_style": dna.camera_style,
            "motion_style": dna.motion_style,
            "emotion_style": dna.emotion_style,
            "audience_relationship": dna.audience_relationship,
            "cta_style": dna.cta_style,
            "content_frequency": dna.content_frequency,
            "asset_freshness_policy": dna.asset_freshness_policy,
            "prompt_dna": dict(dna.prompt_dna),
            "updated_at": _now(),
        })
        return dna

    def get_creative_dna(self, account_id: str, platform: str) -> PlatformCreativeDNA | None:
        from scripts.db.models import PlatformCreativeDNARecord

        with self._session() as session:
            row = session.execute(
                select(PlatformCreativeDNARecord).where(
                    PlatformCreativeDNARecord.account_id == account_id,
                    PlatformCreativeDNARecord.platform == platform,
                )
            ).scalar_one_or_none()
            return _dna_from_row(row) if row else None

    def save_prompt(self, package: PromptPackage) -> PromptPackage:
        from scripts.db.models import PromptPackageRecord

        self._require_account(package.account_id)
        self._upsert(PromptPackageRecord, "prompt_id", package.prompt_id, {
            "account_id": package.account_id,
            "platform": package.platform,
            "kind": package.kind,
            "character_id": package.character_id,
            "world_id": package.world_id,
            "series_id": package.series_id,
            "episode_id": package.episode_id,
            "character_lock": package.character_lock,
            "world_lock": package.world_lock,
            "scene_prompt": package.scene_prompt,
            "visual_style": package.visual_style,
            "camera": package.camera,
            "motion": package.motion,
            "composition": package.composition,
            "lighting": package.lighting,
            "negative_prompt": package.negative_prompt,
            "lens": package.lens,
            "material_texture": package.material_texture,
            "authenticity": package.authenticity,
            "shot_list": list(package.shot_list),
            "temporal_sequence": package.temporal_sequence,
            "camera_movement": package.camera_movement,
            "character_motion": package.character_motion,
            "environment_motion": package.environment_motion,
            "start_state": package.start_state,
            "end_state": package.end_state,
            "duration": package.duration,
            "aspect_ratio": package.aspect_ratio,
            "copy_ready": package.copy_ready,
            "reference_assets": list(package.reference_assets),
            "source_assets": list(package.source_assets),
            "source_asset_id": package.source_asset_id,
            "recommended_model": package.recommended_model,
            "recommended_size": package.recommended_size,
            "recommended_ratio": package.recommended_ratio,
            "recommended_duration": package.recommended_duration,
            "learning_basis": list(package.learning_basis),
            "prompt_patterns": list(package.prompt_patterns),
            "lechuang_parameters": dict(package.lechuang_parameters),
            "prompt_hash": package.prompt_hash,
            "version": int(package.version or 1),
            "parent_prompt_id": package.parent_prompt_id,
        })
        return package

    def get_prompt(self, prompt_id: str) -> PromptPackage | None:
        from scripts.db.models import PromptPackageRecord

        with self._session() as session:
            row = session.get(PromptPackageRecord, prompt_id)
            return _prompt_from_row(row) if row else None

    def save_prompt_pattern(self, pattern: PromptPattern) -> PromptPattern:
        from scripts.db.models import PromptPatternRecord

        if pattern.account_id:
            self._require_account(pattern.account_id)
        self._upsert(PromptPatternRecord, "pattern_id", pattern.pattern_id, {
            "platform": pattern.platform,
            "account_id": pattern.account_id,
            "category": pattern.category,
            "prompt_fragment": pattern.prompt_fragment,
            "positive_count": pattern.positive_count,
            "negative_count": pattern.negative_count,
            "confidence": pattern.confidence,
            "source_episode_ids": list(pattern.source_episode_ids),
            "global_pattern": bool(pattern.global_pattern),
            "promotion_status": pattern.promotion_status or "PLATFORM",
            "sample_count": int(pattern.sample_count or 0),
            "updated_at": _now(),
        })
        return pattern

    def list_prompt_patterns(self, *, platform: str, account_id: str | None = None) -> list[PromptPattern]:
        from scripts.db.models import PromptPatternRecord

        with self._session() as session:
            stmt = select(PromptPatternRecord).where(
                (PromptPatternRecord.platform == platform) | (PromptPatternRecord.global_pattern.is_(True)) | (PromptPatternRecord.platform == "GLOBAL")
            )
            if account_id:
                stmt = stmt.where((PromptPatternRecord.account_id == account_id) | (PromptPatternRecord.account_id.is_(None)) | (PromptPatternRecord.global_pattern.is_(True)))
            rows = list(session.execute(stmt).scalars())
        patterns = [_pattern_from_row(row) for row in rows]
        return [item for item in patterns if item.global_pattern or item.platform in {platform, "GLOBAL"}]

    def save_learning_profile(self, profile: PlatformLearningProfile) -> PlatformLearningProfile:
        from scripts.db.models import PlatformLearningProfileRecord

        self._require_account(profile.account_id)
        self._upsert(PlatformLearningProfileRecord, "profile_id", profile.profile_id, {
            "account_id": profile.account_id,
            "platform": profile.platform,
            "successful_patterns": list(profile.successful_patterns),
            "failed_patterns": list(profile.failed_patterns),
            "high_performance_topics": list(profile.high_performance_topics),
            "high_performance_hooks": list(profile.high_performance_hooks),
            "high_performance_visuals": list(profile.high_performance_visuals),
            "audience_preferences": list(profile.audience_preferences),
            "avoid_patterns": list(profile.avoid_patterns),
            "prompt_patterns": list(profile.prompt_patterns),
            "updated_at": _now(),
        })
        return profile

    def get_learning_profile(self, account_id: str, platform: str) -> PlatformLearningProfile | None:
        from scripts.db.models import PlatformLearningProfileRecord

        with self._session() as session:
            row = session.execute(
                select(PlatformLearningProfileRecord).where(
                    PlatformLearningProfileRecord.account_id == account_id,
                    PlatformLearningProfileRecord.platform == platform,
                )
            ).scalar_one_or_none()
            return _learning_from_row(row) if row else None

    def save_package_asset(self, mapping: ContentPackageAsset) -> ContentPackageAsset:
        from scripts.db.models import ContentPackageAssetRecord

        self._upsert(ContentPackageAssetRecord, "mapping_id", mapping.mapping_id, {
            "package_id": mapping.package_id,
            "asset_id": mapping.asset_id,
            "role": mapping.role,
            "selected": bool(mapping.selected),
        })
        return mapping

    def list_package_assets(self, package_id: str) -> list[ContentPackageAsset]:
        from scripts.db.models import ContentPackageAssetRecord

        with self._session() as session:
            rows = session.execute(select(ContentPackageAssetRecord).where(ContentPackageAssetRecord.package_id == package_id)).scalars()
            return [_package_asset_from_row(row) for row in rows]

    def save_media_asset(self, asset) -> Any:
        from scripts.db.models import MediaAssetRecord

        payload = {
            "sha256": asset.sha256,
            "type": asset.type,
            "path": asset.path,
            "mime_type": asset.mime_type,
            "size": asset.size,
            "width": asset.width,
            "height": asset.height,
            "duration": asset.duration,
            "fps": asset.fps,
            "workflow_id": asset.workflow_id,
            "workflow_version": asset.workflow_version,
            "creative_run_id": asset.creative_run_id,
            "prompt_id": asset.prompt_id,
            "character_id": asset.character_id,
            "metadata_json": dict(asset.metadata or {}),
            "account_id": asset.account_id,
            "series_id": asset.series_id,
            "episode_id": asset.episode_id,
            "content_package_id": asset.content_package_id,
            "creative_context_id": asset.creative_context_id,
            "world_id": asset.world_id,
            "provider": asset.provider or "",
            "provider_task_id": asset.provider_task_id or "",
            "model": asset.model or "",
            "platform": getattr(asset, "platform", "") or "",
            "scope_type": getattr(asset, "scope_type", "") or "PLATFORM_ACCOUNT",
            "asset_role": getattr(asset, "asset_role", "") or "",
            "lifecycle": getattr(asset, "lifecycle", "") or "DRAFT",
            "pool_id": getattr(asset, "pool_id", None),
            "parent_asset_id": getattr(asset, "parent_asset_id", None),
            "source_asset_id": getattr(asset, "source_asset_id", None),
            "generation_mode": getattr(asset, "generation_mode", "") or "",
            "tool": getattr(asset, "tool", "") or "",
            "technical_score": asset.technical_score,
            "visual_score": asset.visual_score,
            "content_score": asset.content_score,
            "platform_score": asset.platform_score,
            "overall_score": asset.overall_score,
        }
        with self._session() as session:
            by_hash = session.execute(select(MediaAssetRecord).where(MediaAssetRecord.sha256 == asset.sha256)).scalar_one_or_none()
            existing = by_hash or session.get(MediaAssetRecord, asset.asset_id)
            if existing is None:
                session.add(MediaAssetRecord(asset_id=asset.asset_id, **payload))
                session.commit()
                return asset
            from creative.store import _asset_from_row
            if existing.sha256 != asset.sha256:
                raise ExistingAssetError("EXISTING_ASSET", f"EXISTING_ASSET sha256={existing.sha256} asset_id={existing.asset_id}")
            if existing.asset_id != asset.asset_id:
                raise ExistingAssetError("EXISTING_ASSET", f"EXISTING_ASSET sha256={existing.sha256} asset_id={existing.asset_id}")
            for key in (
                "lifecycle", "asset_role", "prompt_id", "content_package_id",
                "technical_score", "visual_score", "content_score", "platform_score", "overall_score",
                "width", "height", "duration", "fps", "mime_type", "size",
            ):
                if payload.get(key) not in {None, ""}:
                    setattr(existing, key, payload[key])
            session.commit()
            return _asset_from_row(existing)

    def get_asset_by_sha256(self, sha256: str):
        from scripts.db.models import MediaAssetRecord
        from creative.store import _asset_from_row

        with self._session() as session:
            row = session.execute(select(MediaAssetRecord).where(MediaAssetRecord.sha256 == sha256)).scalar_one_or_none()
            return _asset_from_row(row) if row else None

    def get_media_asset(self, asset_id: str):
        from scripts.db.models import MediaAssetRecord
        from creative.store import _asset_from_row

        with self._session() as session:
            row = session.get(MediaAssetRecord, asset_id)
            return _asset_from_row(row) if row else None

    def list_scoped_assets(
        self,
        *,
        account_id: str,
        platform: str,
        role: str | None = None,
        episode_id: str | None = None,
        lifecycle: str | None = None,
        include_global: bool = True,
    ):
        from scripts.db.models import MediaAssetRecord
        from creative.store import _asset_from_row

        with self._session() as session:
            stmt = select(MediaAssetRecord)
            if include_global:
                stmt = stmt.where(
                    ((MediaAssetRecord.account_id == account_id) & ((MediaAssetRecord.platform == platform) | (MediaAssetRecord.platform == "")))
                    | (MediaAssetRecord.scope_type == "GLOBAL")
                )
            else:
                stmt = stmt.where(MediaAssetRecord.account_id == account_id, MediaAssetRecord.platform == platform)
            if role:
                stmt = stmt.where(MediaAssetRecord.asset_role == role)
            if episode_id:
                stmt = stmt.where(MediaAssetRecord.episode_id == episode_id)
            if lifecycle:
                stmt = stmt.where(MediaAssetRecord.lifecycle == lifecycle)
            rows = list(session.execute(stmt).scalars())
        assets = [_asset_from_row(row) for row in rows]
        owned = []
        for asset in assets:
            if (asset.scope_type or "").upper() == "GLOBAL":
                owned.append(asset)
                continue
            if asset.account_id != account_id:
                continue
            if asset.platform and asset.platform != platform:
                continue
            if role == "GENERATED_PRIMARY" and asset.platform != platform:
                continue
            owned.append(asset)
        return owned

    def get_package(self, package_id: str) -> ContentPackage | None:
        from scripts.db.models import ContentPackageRecord
        from sqlalchemy import inspect as sa_inspect

        if "content_packages" not in sa_inspect(self.engine).get_table_names():
            return None
        with self._session() as session:
            row = session.get(ContentPackageRecord, package_id)
            return _content_package_from_row(row) if row else None

    def save_production_run(self, run: ProductionRun) -> ProductionRun:
        from scripts.db.models import ProductionRunRecord

        self._require_account(run.account_id)
        self._upsert(ProductionRunRecord, "run_id", run.run_id, {
            "account_id": run.account_id,
            "platform": run.platform,
            "episode_id": run.episode_id,
            "prompt_id": run.prompt_id,
            "asset_id": run.asset_id,
            "package_id": run.package_id,
            "handoff_id": run.handoff_id,
            "publication_id": run.publication_id,
            "analytics_id": run.analytics_id,
            "learning_id": run.learning_id,
            "task_id": run.task_id,
            "status": run.status,
            "request": run.request,
            "updated_at": _now(),
        })
        return run

    def get_production_run(self, run_id: str) -> ProductionRun | None:
        from scripts.db.models import ProductionRunRecord

        with self._session() as session:
            row = session.get(ProductionRunRecord, run_id)
            return _production_run_from_row(row) if row else None

    def save_evidence(self, evidence: ProductionEvidence) -> ProductionEvidence:
        from scripts.db.models import ProductionEvidenceRecord

        self._require_account(evidence.account_id)
        self._upsert(ProductionEvidenceRecord, "evidence_id", evidence.evidence_id, {
            "kind": evidence.kind,
            "account_id": evidence.account_id,
            "platform": evidence.platform,
            "status": evidence.status,
            "episode_id": evidence.episode_id,
            "prompt_id": evidence.prompt_id,
            "asset_id": evidence.asset_id,
            "package_id": evidence.package_id,
            "handoff_id": evidence.handoff_id,
            "publication_id": evidence.publication_id,
            "analytics_id": evidence.analytics_id,
            "learning_id": evidence.learning_id,
            "production_run_id": evidence.production_run_id,
            "source": evidence.source,
            "detail": dict(evidence.detail),
        })
        return evidence

    def list_evidence(self, *, account_id: str, episode_id: str | None = None, kind: str | None = None) -> list[ProductionEvidence]:
        from scripts.db.models import ProductionEvidenceRecord

        with self._session() as session:
            stmt = select(ProductionEvidenceRecord).where(ProductionEvidenceRecord.account_id == account_id)
            if episode_id:
                stmt = stmt.where(ProductionEvidenceRecord.episode_id == episode_id)
            if kind:
                stmt = stmt.where(ProductionEvidenceRecord.kind == kind)
            return [_evidence_from_row(row) for row in session.execute(stmt).scalars()]

    def save_analytics(self, record: AnalyticsRecord) -> AnalyticsRecord:
        from scripts.db.models import AnalyticsRecordRow

        self._require_account(record.account_id)
        if record.publication_id and record.observed_at:
            existing = self.get_analytics_observation(record.publication_id, record.observed_at)
            if existing is not None:
                return existing
        self._upsert(AnalyticsRecordRow, "analytics_id", record.analytics_id, {
            "account_id": record.account_id,
            "platform": record.platform,
            "episode_id": record.episode_id,
            "package_id": record.package_id,
            "handoff_id": record.handoff_id,
            "publication_id": record.publication_id,
            "impressions": record.impressions,
            "likes": record.likes,
            "favorites": record.favorites,
            "comments": record.comments,
            "shares": record.shares,
            "clicks": record.clicks,
            "followers_gained": record.followers_gained,
            "followers_delta": record.followers_delta,
            "published_at": record.published_at,
            "observed_at": record.observed_at,
            "topic": record.topic,
            "cover": record.cover,
            "prompt_pattern": record.prompt_pattern,
            "source": record.source,
        })
        return record

    def get_analytics(self, analytics_id: str) -> AnalyticsRecord | None:
        from scripts.db.models import AnalyticsRecordRow

        with self._session() as session:
            row = session.get(AnalyticsRecordRow, analytics_id)
            return _analytics_from_row(row) if row else None

    def get_analytics_observation(self, publication_id: str, observed_at: str) -> AnalyticsRecord | None:
        from scripts.db.models import AnalyticsRecordRow

        with self._session() as session:
            row = session.execute(
                select(AnalyticsRecordRow).where(
                    AnalyticsRecordRow.publication_id == publication_id,
                    AnalyticsRecordRow.observed_at == observed_at,
                )
            ).scalar_one_or_none()
            return _analytics_from_row(row) if row else None

    def list_analytics(self, *, account_id: str, platform: str | None = None) -> list[AnalyticsRecord]:
        from scripts.db.models import AnalyticsRecordRow

        with self._session() as session:
            stmt = select(AnalyticsRecordRow).where(AnalyticsRecordRow.account_id == account_id)
            if platform:
                stmt = stmt.where(AnalyticsRecordRow.platform == platform)
            return [_analytics_from_row(row) for row in session.execute(stmt).scalars()]

    def list_task_history(self, *, account_id: str, task_id: str | None = None) -> list[LifecycleTransition]:
        from scripts.db.models import LifecycleTransitionRecord

        with self._session() as session:
            stmt = select(LifecycleTransitionRecord).where(LifecycleTransitionRecord.account_id == account_id)
            if task_id:
                stmt = stmt.where(
                    (LifecycleTransitionRecord.task_id == task_id)
                    | (LifecycleTransitionRecord.evidence_id == task_id)
                )
            rows = list(session.execute(stmt).scalars())
        return [
            LifecycleTransition(
                transition_id=row.transition_id,
                episode_id=row.episode_id,
                account_id=row.account_id,
                from_status=row.from_status,
                to_status=row.to_status,
                owner=row.owner,
                evidence_id=row.evidence_id,
                task_id=getattr(row, "task_id", None),
                reason=getattr(row, "reason", "") or "",
                operator=getattr(row, "operator", "") or "",
                created_at=_iso(row.created_at),
            )
            for row in rows
        ]

    def get_receipt_for_asset(self, asset_id: str) -> CreativeExecutionReceipt | None:
        from scripts.db.models import CreativeExecutionReceiptRecord

        with self._session() as session:
            row = session.execute(
                select(CreativeExecutionReceiptRecord).where(CreativeExecutionReceiptRecord.asset_id == asset_id)
            ).scalars().first()
            if row is None:
                return None
            return CreativeExecutionReceipt(
                receipt_id=row.receipt_id,
                asset_id=row.asset_id,
                prompt_id=row.prompt_id,
                tool=row.tool,
                model=row.model or "UNKNOWN",
                generated_at=_iso(row.generated_at),
                operator=row.operator,
                source_asset_id=row.source_asset_id,
                generation_mode=row.generation_mode,
                production_run_id=getattr(row, "production_run_id", None),
                created_at=_iso(row.created_at),
            )

    def save_learning(self, record: LearningRecord) -> LearningRecord:
        from scripts.db.models import LearningRecordRow

        self._require_account(record.account_id)
        self._upsert(LearningRecordRow, "learning_id", record.learning_id, {
            "account_id": record.account_id,
            "platform": record.platform,
            "episode_id": record.episode_id,
            "analytics_id": record.analytics_id,
            "prompt_id": record.prompt_id,
            "asset_id": record.asset_id,
            "pattern_ids": list(record.pattern_ids),
            "what_worked": record.what_worked,
            "what_failed": record.what_failed,
            "visual_learning": record.visual_learning,
            "content_learning": record.content_learning,
            "prompt_learning": record.prompt_learning,
            "audience_learning": record.audience_learning,
            "next_recommendation": record.next_recommendation,
            "reason": record.reason,
            "source_episode_ids": list(record.source_episode_ids),
            "evidence_status": record.evidence_status,
            "failure_type": record.failure_type,
            "diagnosis": record.diagnosis,
            "root_cause": record.root_cause,
            "evidence_gap": record.evidence_gap,
            "outcome": record.outcome,
        })
        return record

    def list_learning(self, *, account_id: str, platform: str | None = None) -> list[LearningRecord]:
        from scripts.db.models import LearningRecordRow

        with self._session() as session:
            stmt = select(LearningRecordRow).where(LearningRecordRow.account_id == account_id)
            if platform:
                stmt = stmt.where((LearningRecordRow.platform == platform) | (LearningRecordRow.platform == "GLOBAL"))
            return [_learning_record_from_row(row) for row in session.execute(stmt).scalars()]

    def save_receipt(self, receipt: CreativeExecutionReceipt) -> CreativeExecutionReceipt:
        from scripts.db.models import CreativeExecutionReceiptRecord

        self._upsert(CreativeExecutionReceiptRecord, "receipt_id", receipt.receipt_id, {
            "asset_id": receipt.asset_id,
            "prompt_id": receipt.prompt_id,
            "tool": receipt.tool,
            "model": receipt.model or "UNKNOWN",
            "generated_at": _parse_dt(receipt.generated_at),
            "operator": receipt.operator,
            "source_asset_id": receipt.source_asset_id,
            "generation_mode": receipt.generation_mode,
            "production_run_id": receipt.production_run_id,
        })
        return receipt

    def save_character_revision(self, revision: CharacterRevision) -> CharacterRevision:
        from scripts.db.models import CharacterRevisionRecord

        self._require_account(revision.account_id)
        self._upsert(CharacterRevisionRecord, "revision_id", revision.revision_id, {
            "character_id": revision.character_id,
            "account_id": revision.account_id,
            "version": revision.version,
            "snapshot": dict(revision.snapshot),
        })
        return revision

    def list_character_revisions(self, character_id: str) -> list[CharacterRevision]:
        from scripts.db.models import CharacterRevisionRecord

        with self._session() as session:
            stmt = select(CharacterRevisionRecord).where(CharacterRevisionRecord.character_id == character_id)
            rows = list(session.execute(stmt).scalars())
        rows.sort(key=lambda item: item.version)
        return [
            CharacterRevision(
                revision_id=row.revision_id,
                character_id=row.character_id,
                account_id=row.account_id,
                version=int(row.version or 1),
                snapshot=_json(row.snapshot, {}),
                created_at=_iso(row.created_at),
            )
            for row in rows
        ]

    def save_world_revision(self, revision: WorldRevision) -> WorldRevision:
        from scripts.db.models import WorldRevisionRecord

        self._require_account(revision.account_id)
        self._upsert(WorldRevisionRecord, "revision_id", revision.revision_id, {
            "world_id": revision.world_id,
            "account_id": revision.account_id,
            "version": revision.version,
            "snapshot": dict(revision.snapshot),
        })
        return revision

    def list_world_revisions(self, world_id: str) -> list[WorldRevision]:
        from scripts.db.models import WorldRevisionRecord

        with self._session() as session:
            stmt = select(WorldRevisionRecord).where(WorldRevisionRecord.world_id == world_id)
            rows = list(session.execute(stmt).scalars())
        rows.sort(key=lambda item: item.version)
        return [
            WorldRevision(
                revision_id=row.revision_id,
                world_id=row.world_id,
                account_id=row.account_id,
                version=int(row.version or 1),
                snapshot=_json(row.snapshot, {}),
                created_at=_iso(row.created_at),
            )
            for row in rows
        ]

    def save_reference_snapshot(self, snapshot: AssetReferenceSnapshot) -> AssetReferenceSnapshot:
        from scripts.db.models import AssetReferenceSnapshotRecord

        self._upsert(AssetReferenceSnapshotRecord, "snapshot_id", snapshot.snapshot_id, {
            "prompt_id": snapshot.prompt_id,
            "asset_id": snapshot.asset_id,
            "role": snapshot.role,
            "reason": snapshot.reason,
            "prompt_influence": snapshot.prompt_influence,
        })
        return snapshot

    def save_pattern_promotion(self, promotion: PatternPromotion) -> PatternPromotion:
        from scripts.db.models import PatternPromotionRecord

        self._upsert(PatternPromotionRecord, "promotion_id", promotion.promotion_id, {
            "pattern_id": promotion.pattern_id,
            "platform": promotion.platform,
            "status": promotion.status,
            "sample_count": promotion.sample_count,
            "cross_platform_evidence": list(promotion.cross_platform_evidence),
            "confidence": promotion.confidence,
            "reason": promotion.reason,
            "updated_at": _now(),
        })
        return promotion

    def save_lifecycle(self, transition: LifecycleTransition) -> LifecycleTransition:
        from scripts.db.models import LifecycleTransitionRecord

        self._require_account(transition.account_id)
        self._upsert(LifecycleTransitionRecord, "transition_id", transition.transition_id, {
            "episode_id": transition.episode_id,
            "account_id": transition.account_id,
            "from_status": transition.from_status,
            "to_status": transition.to_status,
            "owner": transition.owner,
            "evidence_id": transition.evidence_id,
            "task_id": transition.task_id,
            "reason": transition.reason,
            "operator": transition.operator,
        })
        return transition

    def save_account_profile(self, profile: AccountProfile) -> AccountProfile:
        from scripts.db.models import AccountProfileRecord

        self._require_account(profile.account_id)
        self._upsert(AccountProfileRecord, "account_id", profile.account_id, {
            "platform": profile.platform,
            "display_name": profile.display_name,
            "external_account_id": profile.external_account_id,
            "status": profile.status,
            "character_id": profile.character_id,
            "world_id": profile.world_id,
            "series_id": profile.series_id,
            "account_objective": profile.account_objective.as_dict(),
            "target_audience": profile.target_audience.as_dict(),
            "positioning": profile.positioning.as_dict(),
            "content_pillars": profile.content_pillars.as_dict(),
            "brand_voice": profile.brand_voice.as_dict(),
            "visual_style": profile.visual_style.as_dict(),
            "content_frequency": profile.content_frequency.as_dict(),
            "preferred_publish_windows": profile.preferred_publish_windows.as_dict(),
            "content_formats": profile.content_formats.as_dict(),
            "operating_rules": profile.operating_rules.as_dict(),
            "forbidden_rules": profile.forbidden_rules.as_dict(),
            "manual_notes": profile.manual_notes.as_dict(),
            "updated_at": _now(),
        })
        return profile

    def get_account_profile(self, account_id: str) -> AccountProfile | None:
        from scripts.db.models import AccountProfileRecord

        with self._session() as session:
            row = session.get(AccountProfileRecord, account_id)
            return _account_profile_from_row(row) if row else None

    def save_operating_state(self, state: AccountOperatingState) -> AccountOperatingState:
        from scripts.db.models import AccountOperatingStateRecord

        self._require_account(state.account_id)
        self._upsert(AccountOperatingStateRecord, "account_id", state.account_id, {
            "platform": state.platform,
            "current_objective": state.current_objective,
            "current_priority": state.current_priority,
            "current_series": state.current_series,
            "current_episode": state.current_episode,
            "current_task": state.current_task,
            "current_campaign": state.current_campaign,
            "current_strategy": state.current_strategy,
            "current_content_status": state.current_content_status,
            "last_published_episode": state.last_published_episode,
            "last_generated_asset": state.last_generated_asset,
            "last_learning": state.last_learning,
            "learning_summary": state.learning_summary,
            "next_action": state.next_action,
            "next_due_at": state.next_due_at,
            "paused_until": state.paused_until,
            "operator_notes": state.operator_notes,
            "updated_at": _now(),
        })
        return state

    def get_operating_state(self, account_id: str) -> AccountOperatingState | None:
        from scripts.db.models import AccountOperatingStateRecord

        with self._session() as session:
            row = session.get(AccountOperatingStateRecord, account_id)
            return _operating_state_from_row(row) if row else None

    def save_override(self, override: ManualOverride) -> ManualOverride:
        from scripts.db.models import ManualOverrideRecord

        self._require_account(override.account_id)
        self._upsert(ManualOverrideRecord, "override_id", override.override_id, {
            "account_id": override.account_id,
            "platform": override.platform,
            "target_kind": override.target_kind,
            "target_id": override.target_id,
            "field_name": override.field_name,
            "old_value": override.old_value if isinstance(override.old_value, dict) else {"value": override.old_value},
            "new_value": override.new_value if isinstance(override.new_value, dict) else {"value": override.new_value},
            "changed_by": override.changed_by,
            "reason": override.reason,
            "source": override.source,
        })
        return override

    def list_overrides(self, account_id: str, *, target_kind: str | None = None) -> list[ManualOverride]:
        from scripts.db.models import ManualOverrideRecord

        with self._session() as session:
            stmt = select(ManualOverrideRecord).where(ManualOverrideRecord.account_id == account_id)
            if target_kind:
                stmt = stmt.where(ManualOverrideRecord.target_kind == target_kind)
            return [_override_from_row(row) for row in session.execute(stmt).scalars()]

    def save_task(self, task: CreatorTask) -> CreatorTask:
        from scripts.db.models import CreatorTaskRecord

        self._require_account(task.account_id)
        self._upsert(CreatorTaskRecord, "task_id", task.task_id, {
            "account_id": task.account_id,
            "platform": task.platform,
            "task_type": task.task_type,
            "title": task.title,
            "description": task.description,
            "priority": task.priority,
            "status": task.status,
            "due_at": task.due_at,
            "episode_id": task.episode_id,
            "series_id": task.series_id,
            "prompt_id": task.prompt_id,
            "asset_id": task.asset_id,
            "package_id": task.package_id,
            "production_run_id": task.production_run_id,
            "parent_task_id": task.parent_task_id,
            "next_task_id": task.next_task_id,
            "next_task_type": task.next_task_type,
            "dependencies": list(task.dependencies),
            "operator_notes": task.operator_notes,
            "blocked_reason": task.blocked_reason,
            "updated_at": _now(),
            "completed_at": _parse_dt(task.completed_at),
        })
        return task

    def get_task(self, task_id: str) -> CreatorTask | None:
        from scripts.db.models import CreatorTaskRecord

        with self._session() as session:
            row = session.get(CreatorTaskRecord, task_id)
            return _task_from_row(row) if row else None

    def list_tasks(
        self,
        *,
        account_id: str | None = None,
        platform: str | None = None,
        status: str | None = None,
        episode_id: str | None = None,
        open_only: bool = False,
    ) -> list[CreatorTask]:
        from scripts.db.models import CreatorTaskRecord

        with self._session() as session:
            stmt = select(CreatorTaskRecord)
            if account_id:
                stmt = stmt.where(CreatorTaskRecord.account_id == account_id)
            if platform:
                stmt = stmt.where(CreatorTaskRecord.platform == platform)
            if status:
                stmt = stmt.where(CreatorTaskRecord.status == status)
            if episode_id:
                stmt = stmt.where(CreatorTaskRecord.episode_id == episode_id)
            if open_only:
                stmt = stmt.where(CreatorTaskRecord.status.notin_(("DONE", "CANCELLED")))
            rows = [_task_from_row(row) for row in session.execute(stmt).scalars()]
        rows.sort(key=lambda item: (item.due_at or "9999", {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}.get(item.priority, 9), item.created_at or ""))
        return rows

    def save_calendar_entry(self, entry: ContentCalendarEntry) -> ContentCalendarEntry:
        from scripts.db.models import ContentCalendarRecord

        self._require_account(entry.account_id)
        self._upsert(ContentCalendarRecord, "calendar_id", entry.calendar_id, {
            "account_id": entry.account_id,
            "platform": entry.platform,
            "date": entry.date,
            "slot": entry.slot,
            "episode_id": entry.episode_id,
            "task_id": entry.task_id,
            "status": entry.status,
            "topic": entry.topic,
            "format": entry.format,
            "priority": entry.priority,
            "updated_at": _now(),
        })
        return entry

    def get_calendar_entry(self, calendar_id: str) -> ContentCalendarEntry | None:
        from scripts.db.models import ContentCalendarRecord

        with self._session() as session:
            row = session.get(ContentCalendarRecord, calendar_id)
            return _calendar_from_row(row) if row else None

    def list_calendar(self, *, account_id: str | None = None, date: str | None = None, platform: str | None = None) -> list[ContentCalendarEntry]:
        from scripts.db.models import ContentCalendarRecord

        with self._session() as session:
            stmt = select(ContentCalendarRecord)
            if account_id:
                stmt = stmt.where(ContentCalendarRecord.account_id == account_id)
            if date:
                stmt = stmt.where(ContentCalendarRecord.date == date)
            if platform:
                stmt = stmt.where(ContentCalendarRecord.platform == platform)
            rows = [_calendar_from_row(row) for row in session.execute(stmt).scalars()]
        rows.sort(key=lambda item: (item.date, item.slot, item.platform))
        return rows

    def save_readiness(self, record: ProductionReadinessRecord) -> ProductionReadinessRecord:
        from scripts.db.models import ProductionReadinessRecordRow

        self._upsert(ProductionReadinessRecordRow, "record_id", record.record_id, {
            "account_id": record.account_id,
            "platform": record.platform,
            "core_production": record.core_production,
            "post_production": record.post_production,
            "full_loop": record.full_loop,
            "checks": dict(record.checks),
            "detail": dict(record.detail),
        })
        return record

    def _require_account(self, account_id: str) -> PlatformAccount:
        account = self.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        return account


def _account_from_row(row) -> PlatformAccount:
    return PlatformAccount(
        account_id=row.account_id,
        platform=row.platform,
        external_account_id=row.external_account_id or "",
        display_name=row.display_name or "",
        status=row.status,
        credential_ref=row.credential_ref or "",
        character_id=row.character_id,
        world_id=row.world_id,
        series_id=getattr(row, "series_id", None),
        default_style_profile_id=row.default_style_profile_id,
        social_account_id=row.social_account_id,
        activated_at=_iso(row.activated_at),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _character_from_row(row) -> VirtualCharacter:
    return VirtualCharacter(
        character_id=row.character_id,
        account_id=row.account_id,
        name=row.name,
        gender=row.gender or "",
        age_range=row.age_range or "",
        appearance_profile=_json(row.appearance_profile, {}),
        body_profile=_json(row.body_profile, {}),
        face_profile=_json(row.face_profile, {}),
        hair_profile=_json(row.hair_profile, {}),
        skin_profile=_json(row.skin_profile, {}),
        clothing_profile=_json(row.clothing_profile, {}),
        personality_profile=_json(row.personality_profile, {}),
        background_story=row.background_story or "",
        speaking_style=row.speaking_style or "",
        behavioral_traits=_tuple(row.behavioral_traits),
        visual_identity_rules=_json(row.visual_identity_rules, {}),
        forbidden_changes=_tuple(row.forbidden_changes),
        reference_asset_ids=_tuple(row.reference_asset_ids),
        derived_from_character_id=getattr(row, "derived_from_character_id", None),
        occupation=getattr(row, "occupation", "") or "",
        location=getattr(row, "location", "") or "",
        values=_tuple(getattr(row, "values", None)),
        behavior=getattr(row, "behavior", "") or "",
        speech=getattr(row, "speech", "") or "",
        style=_json(getattr(row, "style", None), {}),
        accessories=_tuple(getattr(row, "accessories", None)),
        photography=getattr(row, "photography", "") or "",
        lighting=getattr(row, "lighting", "") or "",
        platform_personality=getattr(row, "platform_personality", "") or "",
        content_behavior=getattr(row, "content_behavior", "") or "",
        audience_relationship=getattr(row, "audience_relationship", "") or "",
        continuity_rules=_json(getattr(row, "continuity_rules", None), {}),
        character_dna=_json(getattr(row, "character_dna", None), {}),
        status=row.status,
        version=int(row.version or 1),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _world_from_row(row) -> AccountWorld:
    return AccountWorld(
        world_id=row.world_id,
        account_id=row.account_id,
        name=row.name,
        world_description=row.world_description or "",
        core_theme=row.core_theme or "",
        values=_tuple(row.values),
        tone=row.tone or "",
        visual_language=_json(row.visual_language, {}),
        locations=_tuple(row.locations),
        daily_life_rules=_tuple(row.daily_life_rules),
        story_rules=_tuple(row.story_rules),
        audience=row.audience or "",
        taboos=_tuple(row.taboos),
        brand_rules=_tuple(row.brand_rules),
        city=getattr(row, "city", "") or "",
        season=getattr(row, "season", "") or "",
        time_of_day=getattr(row, "time_of_day", "") or "",
        lighting=getattr(row, "lighting", "") or "",
        lifestyle=getattr(row, "lifestyle", "") or "",
        social_relations=_tuple(getattr(row, "social_relations", None)),
        world_dna=_json(getattr(row, "world_dna", None), {}),
        status=row.status,
        version=int(row.version or 1),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _series_from_row(row) -> ContentSeries:
    return ContentSeries(
        series_id=row.series_id,
        account_id=row.account_id,
        world_id=row.world_id,
        name=row.name,
        description=row.description or "",
        series_type=row.series_type or "serial",
        content_rules=_json(row.content_rules, {}),
        continuity_rules=_json(row.continuity_rules, {}),
        status=row.status,
        start_date=row.start_date,
        end_date=row.end_date,
        current_episode_no=int(row.current_episode_no or 0),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _episode_from_row(row) -> Episode:
    return Episode(
        episode_id=row.episode_id,
        series_id=row.series_id,
        episode_no=int(row.episode_no),
        title=row.title or "",
        brief=row.brief or "",
        previous_episode_id=row.previous_episode_id,
        next_episode_id=row.next_episode_id,
        continuity_context=_json(row.continuity_context, {}),
        character_state=_json(row.character_state, {}),
        world_state=_json(row.world_state, {}),
        location_state=_json(row.location_state, {}),
        visual_state=_json(row.visual_state, {}),
        story_state=_json(row.story_state, {}),
        content_status=row.content_status,
        account_id=row.account_id or "",
        campaign_id=row.campaign_id,
        content_package_id=row.content_package_id,
        primary_asset_id=getattr(row, "primary_asset_id", None),
        prompt_id=getattr(row, "prompt_id", None),
        character_revision=getattr(row, "character_revision", None),
        world_revision=getattr(row, "world_revision", None),
        production_run_id=getattr(row, "production_run_id", None),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _context_from_row(row) -> CreativeContext:
    return CreativeContext(
        context_id=row.context_id,
        account_id=row.account_id,
        platform=row.platform,
        character_id=row.character_id,
        world_id=row.world_id,
        series_id=row.series_id,
        episode_id=row.episode_id,
        campaign_id=row.campaign_id,
        user_request=row.user_request or "",
        creative_request=row.creative_request or "",
        normalized_prompt=row.normalized_prompt or "",
        system_constraints=_json(row.system_constraints, {}),
        character_context=_json(row.character_context, {}),
        world_context=_json(row.world_context, {}),
        continuity_context=_json(row.continuity_context, {}),
        platform_context=_json(row.platform_context, {}),
        generation_parameters=_json(row.generation_parameters, {}),
        provider=row.provider or "",
        model=row.model or "",
        provider_task_id=row.provider_task_id or "",
        resolved_target=_json(row.resolved_target, {}),
        created_at=_iso(row.created_at),
    )


def _revision_from_row(row) -> ContentRevision:
    return ContentRevision(
        revision_id=row.revision_id,
        content_package_id=row.content_package_id,
        version=int(row.version),
        parent_revision_id=row.parent_revision_id,
        change_summary=row.change_summary or "",
        snapshot=_json(row.snapshot, {}),
        created_at=_iso(row.created_at),
        created_by=row.created_by or "meiti",
    )


def _memory_model(kind: str):
    from scripts.db.models import (
        AccountMemoryRecord,
        CharacterMemoryRecord,
        EpisodeMemoryRecord,
        SeriesMemoryRecord,
        WorldMemoryRecord,
    )

    mapping = {
        "account": AccountMemoryRecord,
        "character": CharacterMemoryRecord,
        "world": WorldMemoryRecord,
        "series": SeriesMemoryRecord,
        "episode": EpisodeMemoryRecord,
    }
    if kind not in mapping:
        raise ValueError(f"invalid memory kind: {kind}")
    return mapping[kind]


def _memory_from_row(row) -> ContinuityMemory:
    return ContinuityMemory(
        memory_id=row.memory_id,
        kind=row.kind,
        account_id=row.account_id,
        subject_id=row.subject_id,
        key=row.key,
        value=row.value,
        source=row.source or "continuity",
        created_at=_iso(row.created_at),
    )


def _feedback_from_row(row) -> PerformanceFeedback:
    return PerformanceFeedback(
        feedback_id=row.feedback_id,
        account_id=row.account_id,
        platform=row.platform,
        content_package_id=row.content_package_id or "",
        episode_id=row.episode_id,
        topic=row.topic or "",
        hook=row.hook or "",
        visual_style=row.visual_style or "",
        caption_style=row.caption_style or "",
        duration=None if row.duration is None else float(row.duration),
        scene=row.scene or "",
        action=row.action or "",
        audio=row.audio or "",
        engagement=_json(row.engagement, {}),
        retention=_json(row.retention, {}),
        publication_id=row.publication_id or "",
        created_at=_iso(row.created_at),
    )


def _lineage_from_row(row) -> AssetLineage:
    return AssetLineage(
        lineage_id=row.lineage_id,
        asset_id=row.asset_id,
        account_id=row.account_id,
        series_id=row.series_id,
        episode_id=row.episode_id,
        content_package_id=row.content_package_id,
        creative_context_id=row.creative_context_id,
        character_id=row.character_id,
        world_id=row.world_id,
        user_request=row.user_request or "",
        generation_request=_json(row.generation_request, {}),
        provider=row.provider or "",
        provider_task_id=row.provider_task_id or "",
        model=row.model or "",
        attempt_no=int(row.attempt_no or 1),
        parent_asset_id=row.parent_asset_id or None,
        qa_decision=row.qa_decision or "",
        published=bool(row.published),
        selected_for_package=bool(getattr(row, "selected_for_package", False)),
        source_asset_id=getattr(row, "source_asset_id", None),
        workflow_id=getattr(row, "workflow_id", None),
        reference_asset_ids=_tuple(getattr(row, "reference_asset_ids", None)),
        origin_episode_id=getattr(row, "origin_episode_id", None),
        target_episode_id=getattr(row, "target_episode_id", None),
        origin_platform=getattr(row, "origin_platform", "") or "",
        target_platform=getattr(row, "target_platform", "") or "",
        reuse_mode=getattr(row, "reuse_mode", None) or "NONE",
        generation_mode=getattr(row, "generation_mode", "") or "",
        tool=getattr(row, "tool", "") or "",
        prompt_id=getattr(row, "prompt_id", None),
        created_at=_iso(row.created_at),
    )


def _pool_from_row(row) -> PlatformAssetPool:
    return PlatformAssetPool(
        pool_id=row.pool_id,
        account_id=row.account_id,
        platform=row.platform,
        character_id=row.character_id,
        world_id=row.world_id,
        created_at=_iso(row.created_at),
    )


def _dna_from_row(row) -> PlatformCreativeDNA:
    return PlatformCreativeDNA(
        dna_id=row.dna_id,
        account_id=row.account_id,
        platform=row.platform,
        visual_style=_json(row.visual_style, {}),
        copy_style=_json(row.copy_style, {}),
        hook_style=row.hook_style or "",
        camera_style=row.camera_style or "",
        motion_style=row.motion_style or "",
        emotion_style=row.emotion_style or "",
        audience_relationship=row.audience_relationship or "",
        cta_style=row.cta_style or "",
        content_frequency=row.content_frequency or "",
        asset_freshness_policy=row.asset_freshness_policy or "NEW_PRIMARY_ASSET_REQUIRED",
        prompt_dna=_json(row.prompt_dna, {}),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _prompt_from_row(row) -> PromptPackage:
    return PromptPackage(
        prompt_id=row.prompt_id,
        account_id=row.account_id,
        platform=row.platform,
        kind=row.kind or "IMAGE",
        character_id=row.character_id,
        world_id=row.world_id,
        series_id=row.series_id,
        episode_id=row.episode_id,
        character_lock=row.character_lock or "",
        world_lock=row.world_lock or "",
        scene_prompt=row.scene_prompt or "",
        visual_style=row.visual_style or "",
        camera=row.camera or "",
        motion=row.motion or "",
        composition=row.composition or "",
        lighting=row.lighting or "",
        negative_prompt=row.negative_prompt or "",
        lens=row.lens or "",
        material_texture=row.material_texture or "",
        authenticity=row.authenticity or "",
        shot_list=_tuple(row.shot_list),
        temporal_sequence=row.temporal_sequence or "",
        camera_movement=row.camera_movement or "",
        character_motion=row.character_motion or "",
        environment_motion=row.environment_motion or "",
        start_state=row.start_state or "",
        end_state=row.end_state or "",
        duration=row.duration or "",
        aspect_ratio=row.aspect_ratio or "",
        copy_ready=row.copy_ready or "",
        reference_assets=_tuple(row.reference_assets),
        source_assets=_tuple(row.source_assets),
        source_asset_id=row.source_asset_id,
        recommended_model=row.recommended_model or "",
        recommended_size=row.recommended_size or "",
        recommended_ratio=row.recommended_ratio or "",
        recommended_duration=row.recommended_duration or "",
        learning_basis=_tuple(row.learning_basis),
        prompt_patterns=_tuple(row.prompt_patterns),
        lechuang_parameters=_json(row.lechuang_parameters, {}),
        prompt_hash=getattr(row, "prompt_hash", "") or "",
        version=int(getattr(row, "version", 1) or 1),
        parent_prompt_id=getattr(row, "parent_prompt_id", None),
        created_at=_iso(row.created_at),
    )


def _pattern_from_row(row) -> PromptPattern:
    return PromptPattern(
        pattern_id=row.pattern_id,
        platform=row.platform,
        account_id=row.account_id,
        category=row.category or "",
        prompt_fragment=row.prompt_fragment or "",
        positive_count=int(row.positive_count or 0),
        negative_count=int(row.negative_count or 0),
        confidence=float(row.confidence or 0),
        source_episode_ids=_tuple(row.source_episode_ids),
        global_pattern=bool(row.global_pattern),
        promotion_status=getattr(row, "promotion_status", None) or "PLATFORM",
        sample_count=int(getattr(row, "sample_count", 0) or 0),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _learning_from_row(row) -> PlatformLearningProfile:
    return PlatformLearningProfile(
        profile_id=row.profile_id,
        account_id=row.account_id,
        platform=row.platform,
        successful_patterns=_tuple(row.successful_patterns),
        failed_patterns=_tuple(row.failed_patterns),
        high_performance_topics=_tuple(row.high_performance_topics),
        high_performance_hooks=_tuple(row.high_performance_hooks),
        high_performance_visuals=_tuple(row.high_performance_visuals),
        audience_preferences=_tuple(row.audience_preferences),
        avoid_patterns=_tuple(row.avoid_patterns),
        prompt_patterns=_tuple(row.prompt_patterns),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _package_asset_from_row(row) -> ContentPackageAsset:
    return ContentPackageAsset(
        mapping_id=row.mapping_id,
        package_id=row.package_id,
        asset_id=row.asset_id,
        role=row.role or "PRIMARY",
        selected=bool(row.selected),
        created_at=_iso(row.created_at),
    )


def _content_package_from_row(row) -> ContentPackage:
    return ContentPackage(
        package_id=row.package_id,
        title=row.title or "",
        body=row.body or "",
        evidence_ids=_tuple(row.evidence_ids),
        brand_id=row.brand_id,
        creator_id=row.creator_id,
        campaign_id=row.campaign_id,
        topic=row.topic or "",
        content_pillar=row.content_pillar or "",
        hook=row.hook or "",
        format=row.format or "post",
        audience=row.audience or "",
        caption=row.caption or "",
        media_assets=_tuple(row.media_assets),
        commerce_intent=row.commerce_intent or "none",
        variants=_tuple(row.variants),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
        metadata=_json(getattr(row, "metadata_json", None) or getattr(row, "metadata", None), {}),
        account_id=row.account_id,
        series_id=row.series_id,
        episode_id=row.episode_id,
        platform=row.platform or "",
        status=row.status or "DRAFT",
        character_id=row.character_id,
        world_id=row.world_id,
        creative_context_id=row.creative_context_id,
        revision=int(row.revision or 1),
        current_revision=row.current_revision,
        reference_assets=_tuple(getattr(row, "reference_assets", None)),
        primary_assets=_tuple(getattr(row, "primary_assets", None)),
        published_assets=_tuple(getattr(row, "published_assets", None)),
        prompt_id=getattr(row, "prompt_id", None),
    )


def _production_run_from_row(row) -> ProductionRun:
    return ProductionRun(
        run_id=row.run_id,
        account_id=row.account_id,
        platform=row.platform,
        episode_id=row.episode_id,
        prompt_id=row.prompt_id,
        asset_id=row.asset_id,
        package_id=row.package_id,
        handoff_id=row.handoff_id,
        publication_id=row.publication_id,
        analytics_id=row.analytics_id,
        learning_id=row.learning_id,
        task_id=getattr(row, "task_id", None),
        status=row.status or "OPEN",
        request=row.request or "",
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _evidence_from_row(row) -> ProductionEvidence:
    return ProductionEvidence(
        evidence_id=row.evidence_id,
        kind=row.kind,
        account_id=row.account_id,
        platform=row.platform,
        status=row.status or "PASS",
        episode_id=row.episode_id,
        prompt_id=row.prompt_id,
        asset_id=row.asset_id,
        package_id=row.package_id,
        handoff_id=row.handoff_id,
        publication_id=row.publication_id,
        analytics_id=row.analytics_id,
        learning_id=row.learning_id,
        production_run_id=row.production_run_id,
        source=row.source or "operator",
        detail=_json(row.detail, {}),
        created_at=_iso(row.created_at),
    )


def _analytics_from_row(row) -> AnalyticsRecord:
    return AnalyticsRecord(
        analytics_id=row.analytics_id,
        account_id=row.account_id,
        platform=row.platform,
        episode_id=row.episode_id,
        package_id=row.package_id,
        handoff_id=row.handoff_id,
        publication_id=row.publication_id,
        impressions=row.impressions,
        likes=row.likes,
        favorites=row.favorites,
        comments=row.comments,
        shares=row.shares,
        clicks=getattr(row, "clicks", None),
        followers_gained=row.followers_gained,
        followers_delta=getattr(row, "followers_delta", None),
        published_at=row.published_at,
        observed_at=getattr(row, "observed_at", None),
        topic=row.topic or "",
        cover=row.cover or "",
        prompt_pattern=row.prompt_pattern or "",
        source=row.source or "manual",
        created_at=_iso(row.created_at),
    )


def _learning_record_from_row(row) -> LearningRecord:
    return LearningRecord(
        learning_id=row.learning_id,
        account_id=row.account_id,
        platform=row.platform,
        episode_id=row.episode_id,
        analytics_id=row.analytics_id,
        prompt_id=getattr(row, "prompt_id", None),
        asset_id=getattr(row, "asset_id", None),
        pattern_ids=_tuple(row.pattern_ids),
        what_worked=row.what_worked or "",
        what_failed=row.what_failed or "",
        visual_learning=row.visual_learning or "",
        content_learning=row.content_learning or "",
        prompt_learning=row.prompt_learning or "",
        audience_learning=row.audience_learning or "",
        next_recommendation=row.next_recommendation or "",
        reason=row.reason or "",
        source_episode_ids=_tuple(row.source_episode_ids),
        evidence_status=getattr(row, "evidence_status", None) or "NOT_VERIFIED",
        failure_type=getattr(row, "failure_type", "") or "",
        diagnosis=getattr(row, "diagnosis", "") or "",
        root_cause=getattr(row, "root_cause", "") or "",
        evidence_gap=getattr(row, "evidence_gap", "") or "",
        outcome=getattr(row, "outcome", "") or "",
        created_at=_iso(row.created_at),
    )


def _knowledge_from_payload(value: Any) -> KnowledgeField:
    if isinstance(value, KnowledgeField):
        return value
    if isinstance(value, dict) and ("source" in value or "value" in value):
        return KnowledgeField(
            value=value.get("value"),
            source=value.get("source") or "UNKNOWN",
            reason=value.get("reason") or "",
            changed_by=value.get("changed_by") or "",
            changed_at=value.get("changed_at"),
        )
    return KnowledgeField(value=value, source="UNKNOWN")


def _account_profile_from_row(row) -> AccountProfile:
    return AccountProfile(
        account_id=row.account_id,
        platform=row.platform,
        display_name=row.display_name or "",
        external_account_id=row.external_account_id or "",
        status=row.status or "DRAFT",
        character_id=row.character_id,
        world_id=row.world_id,
        series_id=row.series_id,
        account_objective=_knowledge_from_payload(row.account_objective),
        target_audience=_knowledge_from_payload(row.target_audience),
        positioning=_knowledge_from_payload(row.positioning),
        content_pillars=_knowledge_from_payload(row.content_pillars),
        brand_voice=_knowledge_from_payload(row.brand_voice),
        visual_style=_knowledge_from_payload(row.visual_style),
        content_frequency=_knowledge_from_payload(row.content_frequency),
        preferred_publish_windows=_knowledge_from_payload(row.preferred_publish_windows),
        content_formats=_knowledge_from_payload(row.content_formats),
        operating_rules=_knowledge_from_payload(row.operating_rules),
        forbidden_rules=_knowledge_from_payload(row.forbidden_rules),
        manual_notes=_knowledge_from_payload(row.manual_notes),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _operating_state_from_row(row) -> AccountOperatingState:
    return AccountOperatingState(
        account_id=row.account_id,
        platform=row.platform,
        current_objective=row.current_objective or "",
        current_priority=row.current_priority or "NORMAL",
        current_series=row.current_series,
        current_episode=row.current_episode,
        current_task=row.current_task,
        current_campaign=row.current_campaign,
        current_strategy=row.current_strategy or "",
        current_content_status=row.current_content_status or "IDEA",
        last_published_episode=row.last_published_episode,
        last_generated_asset=row.last_generated_asset,
        last_learning=row.last_learning,
        learning_summary=row.learning_summary or "",
        next_action=row.next_action or "",
        next_due_at=row.next_due_at,
        paused_until=row.paused_until,
        operator_notes=row.operator_notes or "",
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _override_from_row(row) -> ManualOverride:
    old_value = _json(row.old_value, {})
    new_value = _json(row.new_value, {})
    if isinstance(old_value, dict) and set(old_value.keys()) == {"value"}:
        old_value = old_value.get("value")
    if isinstance(new_value, dict) and set(new_value.keys()) == {"value"}:
        new_value = new_value.get("value")
    return ManualOverride(
        override_id=row.override_id,
        account_id=row.account_id,
        platform=row.platform,
        target_kind=row.target_kind,
        target_id=row.target_id,
        field_name=row.field_name,
        old_value=old_value,
        new_value=new_value,
        changed_by=row.changed_by or "operator",
        reason=row.reason or "",
        source=row.source or "USER_OVERRIDE",
        created_at=_iso(row.created_at),
    )


def _task_from_row(row) -> CreatorTask:
    return CreatorTask(
        task_id=row.task_id,
        account_id=row.account_id,
        platform=row.platform,
        task_type=row.task_type,
        title=row.title,
        description=row.description or "",
        priority=row.priority or "NORMAL",
        status=row.status or "TODO",
        due_at=row.due_at,
        episode_id=row.episode_id,
        series_id=row.series_id,
        prompt_id=row.prompt_id,
        asset_id=row.asset_id,
        package_id=row.package_id,
        production_run_id=row.production_run_id,
        parent_task_id=row.parent_task_id,
        next_task_id=row.next_task_id,
        next_task_type=row.next_task_type,
        dependencies=_tuple(row.dependencies),
        operator_notes=row.operator_notes or "",
        blocked_reason=row.blocked_reason or "",
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
        completed_at=_iso(row.completed_at),
    )


def _calendar_from_row(row) -> ContentCalendarEntry:
    return ContentCalendarEntry(
        calendar_id=row.calendar_id,
        account_id=row.account_id,
        platform=row.platform,
        date=row.date,
        slot=row.slot or "default",
        episode_id=row.episode_id,
        task_id=row.task_id,
        status=row.status or "PLANNED",
        topic=row.topic or "",
        format=row.format or "image",
        priority=row.priority or "NORMAL",
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )
