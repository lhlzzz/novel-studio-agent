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
    LIFECYCLE_OWNERS,
    AccountContext,
    AccountWorld,
    AnalyticsRecord,
    AssetLineage,
    AssetReferenceSnapshot,
    CharacterRevision,
    ConfigurationBlocked,
    ContentPackage,
    ContentSeries,
    ContinuityMemory,
    Episode,
    IsolationError,
    LearningRecord,
    LifecycleTransition,
    MemoryWritebackError,
    PatternPromotion,
    PerformanceFeedback,
    PlatformAccount,
    PlatformLearningProfile,
    ProductionEvidence,
    ProductionRun,
    PromptPackage,
    PromptPattern,
    ResolvedTarget,
    VirtualCharacter,
    WorldRevision,
    utcnow,
)
from content.platform_policy import differentiate_package, platform_policy
from content.qa import CharacterContinuityQA, CrossAccountIsolationGuard
from content.resolve import IntentResolver
from content.store import ContinuityStore


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
        return saved

    def bind_character(self, account_id: str, character: VirtualCharacter) -> VirtualCharacter:
        self.isolation.assert_owned(account_id=account_id)
        if character.account_id != account_id:
            raise IsolationError("character account_id must match the platform account")
        saved = self.store.save_character(character)
        account = self.store.get_account(account_id)
        self.store.save_account(PlatformAccount(**{**account.__dict__, "character_id": saved.character_id, "updated_at": utcnow()}))
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
        )
        saved = self.store.save_series(series)
        self.store.save_memory(ContinuityMemory(
            memory_id=uuid4().hex,
            kind="series",
            account_id=account_id,
            subject_id=saved.series_id,
            key="series",
            value={"name": saved.name},
        ))
        return saved

    def continue_series(self, *, account_id: str, series_id: str, brief: str = "", title: str = "") -> Episode:
        return self.engine.create_next_episode(series_id, account_id=account_id, brief=brief, title=title)

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
        learning = self.store.get_learning_profile(account_id, platform)
        records = self.store.list_learning(account_id=account_id, platform=platform)
        learning_payload = dict(learning.__dict__) if learning else {}
        if records:
            learning_payload["learning_records"] = [
                {
                    "learning_id": item.learning_id,
                    "platform": item.platform,
                    "what_worked": item.what_worked,
                    "next_recommendation": item.next_recommendation,
                    "reason": item.reason,
                    "source_episode_ids": list(item.source_episode_ids),
                }
                for item in records
                if item.platform in {platform, "GLOBAL"}
            ]
            learning_payload["successful_patterns"] = tuple(
                list(learning_payload.get("successful_patterns") or ())
                + [item.next_recommendation or item.what_worked for item in records if item.what_worked or item.next_recommendation]
            )
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
        )
        if episode is not None:
            self.transition_episode(episode.episode_id, account_id=account_id, to_status="PROMPT_READY")
            run = self.open_production_run(account_id=account_id, platform=platform, episode_id=episode.episode_id, request=request)
            self.store.save_production_run(ProductionRun(**{**run.__dict__, "prompt_id": prompt.prompt_id, "status": "AWAITING_CREATIVE", "updated_at": utcnow()}))
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
        return prompt

    def import_asset(self, path: str, **fields: Any) -> dict[str, Any]:
        return PlatformAssetService(self.store).import_asset(path, **fields)

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
        if package.account_id:
            self.store.save_memory(ContinuityMemory(
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
                    "publication_id": getattr(publication, "publication_id", ""),
                    "external_post_id": getattr(publication, "provider_post_id", ""),
                    "publication_url": getattr(publication, "external_url", ""),
                },
            ))
            if package.episode_id:
                episode = self.store.get_episode(package.episode_id, account_id=package.account_id)
                if episode is not None:
                    self.store.save_episode(Episode(**{**episode.__dict__, "content_status": "PUBLISHED", "updated_at": utcnow()}))
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
            try:
                from memory.service import get_memory_service
                get_memory_service().writeback({
                    "kind": "PUBLICATION_LEARNING",
                    "account_id": package.account_id,
                    "platform": package.platform,
                    "series_id": package.series_id,
                    "episode_id": package.episode_id,
                    "publication_id": getattr(publication, "publication_id", ""),
                    "source": "publication",
                    "content_pattern": {
                        "package_id": package.package_id,
                        "media_asset_ids": list(package.media_assets),
                    },
                })
            except Exception as exc:
                raise MemoryWritebackError("MEMORY_WRITEBACK_FAILED", str(exc)) from exc
        memories = self.store.list_memories(account_id=package.account_id or "", kind="episode") if package.account_id else []
        published = [item for item in memories if item.key == "published"]
        if published:
            return published[-1]
        return ContinuityMemory(memory_id="none", kind="episode", account_id=package.account_id or "", subject_id="", key="published", value={})

    def record_feedback(self, feedback: PerformanceFeedback) -> PerformanceFeedback:
        return self.store.save_feedback(feedback)

    def calendar(self) -> list[dict[str, Any]]:
        rows = []
        for account in self.store.list_accounts():
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
        return {
            "account": account,
            "character": character,
            "world": world,
            "series": series,
            "episode": episode,
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
            status="OPEN",
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
        if package.episode_id:
            self.transition_episode(package.episode_id, account_id=package.account_id, to_status="HANDOFF_READY")
        run = None
        if package.episode_id:
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
            detail={"kind": "handoff", "status": getattr(handoff, "status", "")},
        )

    def record_analytics(self, record: AnalyticsRecord) -> AnalyticsRecord:
        saved = self.store.save_analytics(record)
        if saved.episode_id:
            self.transition_episode(saved.episode_id, account_id=saved.account_id, to_status="ANALYTICS_PENDING")
        self.record_evidence(
            kind="ANALYTICS_IMPORTED",
            account_id=saved.account_id,
            platform=saved.platform,
            episode_id=saved.episode_id,
            package_id=saved.package_id,
            handoff_id=saved.handoff_id,
            publication_id=saved.publication_id,
            analytics_id=saved.analytics_id,
            source="analytics",
        )
        return saved

    def record_learning(self, record: LearningRecord) -> LearningRecord:
        saved = self.store.save_learning(record)
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
        try:
            from memory.service import get_memory_service
            get_memory_service().writeback({
                "kind": "LEARNING_RECORD",
                "account_id": saved.account_id,
                "platform": saved.platform,
                "episode_id": saved.episode_id,
                "source": "analytics",
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
        except Exception as exc:
            raise MemoryWritebackError("MEMORY_WRITEBACK_FAILED", str(exc)) from exc
        if saved.episode_id:
            self.transition_episode(saved.episode_id, account_id=saved.account_id, to_status="LEARNED")
        self.record_evidence(
            kind="LEARNING_WRITTEN",
            account_id=saved.account_id,
            platform=saved.platform,
            episode_id=saved.episode_id,
            analytics_id=saved.analytics_id,
            learning_id=saved.learning_id,
            source="memory",
            detail={"reason": saved.reason, "next_recommendation": saved.next_recommendation},
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
            "LEARNING_RUNTIME": _prod("LEARNING_WRITTEN"),
            "PRODUCTION_EVIDENCE": _arch(ready, count=len(evidence)),
            "REAL_DAY_1": _prod("DAY_001_REAL_ASSET_IMPORTED"),
            "REAL_DAY_2": _prod("DAY_002_REAL_ASSET_IMPORTED"),
            "REAL_DAY_3": _prod("DAY_003_REAL_ASSET_IMPORTED"),
        }

    def packages_for_request(self, text: str) -> list[dict[str, Any]]:
        return [self.prepare_target(target, text=text) for target in self.resolver.resolve_many(text)]


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
