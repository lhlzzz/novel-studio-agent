"""Account-world continuity runtime. Creative generation still goes through CreativeRuntime."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4

from content.continuity import ContinuityEngine
from content.models import (
    AccountContext,
    AccountWorld,
    AssetLineage,
    ContentPackage,
    ContentSeries,
    ContinuityMemory,
    Episode,
    IsolationError,
    PerformanceFeedback,
    PlatformAccount,
    ResolvedTarget,
    VirtualCharacter,
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
        self.store.save_memory(ContinuityMemory(
            memory_id=uuid4().hex,
            kind="character",
            account_id=account_id,
            subject_id=saved.character_id,
            key="identity",
            value={"name": saved.name, "version": saved.version},
        ))
        return saved

    def bind_world(self, account_id: str, world: AccountWorld) -> AccountWorld:
        self.isolation.assert_owned(account_id=account_id)
        if world.account_id != account_id:
            raise IsolationError("world account_id must match the platform account")
        saved = self.store.save_world(world)
        account = self.store.get_account(account_id)
        self.store.save_account(PlatformAccount(**{**account.__dict__, "world_id": saved.world_id, "updated_at": utcnow()}))
        self.store.save_memory(ContinuityMemory(
            memory_id=uuid4().hex,
            kind="world",
            account_id=account_id,
            subject_id=saved.world_id,
            key="world",
            value={"name": saved.name, "theme": saved.core_theme},
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
        }

    def package_from_generation(self, *, context, assets: list[Any], title: str = "", body: str = "", package_id: str | None = None, status: str = "GENERATED") -> ContentPackage:
        paths = tuple(getattr(item, "path", item) for item in assets if item)
        package = ContentPackage(
            package_id=package_id or uuid4().hex,
            title=title or context.creative_request or context.user_request,
            body=body or context.normalized_prompt,
            media_assets=paths,
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
        )
        package = differentiate_package(package, context)
        saved = self.store.save_package(package)
        revision = self.store.save_package_snapshot(saved, change_summary=f"{status} v{saved.revision}")
        package = ContentPackage(**{**saved.__dict__, "revision": revision.version, "current_revision": revision.revision_id})
        if context.episode_id:
            episode = self.store.get_episode(context.episode_id, account_id=context.account_id)
            if episode is not None:
                self.store.save_episode(Episode(**{**episode.__dict__, "content_package_id": package.package_id, "content_status": status, "updated_at": utcnow()}))
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
            except Exception:
                pass
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

    def doctor(self) -> dict[str, Any]:
        from content.store import schema_ready

        ready, missing = schema_ready(self.store.engine)
        accounts = self.store.list_accounts()
        characters = [item for account in accounts for item in self.store.list_characters(account.account_id)]
        worlds = [item for account in accounts for item in self.store.list_worlds(account.account_id)]
        series = [item for account in accounts for item in self.store.list_series(account.account_id)]
        def _status(ok: bool, **extra):
            payload = {"status": "PASS" if ok else "NOT_CONFIGURED"}
            payload.update(extra)
            return payload
        return {
            "ACCOUNT_RUNTIME": _status(ready, count=len(accounts), missing=missing),
            "CHARACTER_RUNTIME": _status(ready, count=len(characters)),
            "WORLD_RUNTIME": _status(ready, count=len(worlds)),
            "SERIES_RUNTIME": _status(ready, count=len(series)),
            "CONTINUITY_RUNTIME": _status(ready and hasattr(self.engine, "build_continuity_bundle")),
            "ASSET_LINEAGE": _status(ready and hasattr(self.store, "allocate_attempt")),
            "PLATFORM_VARIANT": _status(callable(differentiate_package)),
            "CREATIVE_RUNTIME": _status(True, owner="creative.runtime.container.CreativeRuntime"),
            "ACCOUNT_CONTEXT": _status(True, owner="content.models.AccountContext"),
            "MULTI_ACCOUNT_RUNTIME": _status(ready and hasattr(self.store, "select_current_account")),
            "EPISODE_TRANSACTION": _status(ready and hasattr(self.store, "create_next_episode_tx")),
        }

    def packages_for_request(self, text: str) -> list[dict[str, Any]]:
        return [self.prepare_target(target, text=text) for target in self.resolver.resolve_many(text)]
