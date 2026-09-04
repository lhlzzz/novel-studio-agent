"""Platform asset pool, freshness, reference resolution, and manual import."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from content.models import (
    ASSET_LIFECYCLES,
    ASSET_ROLES,
    AssetFreshnessError,
    AssetLineage,
    ConfigurationBlocked,
    ContentPackage,
    ContentPackageAsset,
    CreativeExecutionReceipt,
    CrossPlatformAssetReuse,
    Episode,
    ExistingAssetError,
    FRESHNESS_INTENTS,
    IsolationError,
    ManualOverride,
    PACKAGE_ASSET_ROLES,
    PRIMARY_ASSET_ROLES,
    PlatformAssetPool,
    ProductionEvidence,
    REUSE_INTENTS,
    utcnow,
)
from content.store import ContinuityStore
from creative.assets import persist_file, sha256_file
from creative.judges.technical import TechnicalQA
from creative.schemas import MediaAsset


REFERENCE_ROLES = frozenset({
    "CHARACTER_REFERENCE",
    "WORLD_REFERENCE",
    "STYLE_REFERENCE",
    "SCENE_REFERENCE",
    "SOURCE_REFERENCE",
})
NEW_PRIMARY_ASSET_REQUIRED = True


class AssetFreshnessGuard:
    name = "asset_freshness"

    def inspect(
        self,
        *,
        current_episode: Episode | None,
        candidate: MediaAsset | None,
        previous_episode: Episode | None = None,
        platform: str = "",
        account_id: str = "",
        intent: str = "GENERATE",
        reuse_mode: str = "NONE",
        previous_asset: MediaAsset | None = None,
        store: ContinuityStore | None = None,
    ) -> dict[str, Any]:
        if candidate is None:
            return {"decision": "FAIL", "code": "MISSING_ASSET", "failures": ["missing_candidate"]}
        failures: list[str] = []
        code = ""
        if (candidate.lifecycle or "").upper() in {"ARCHIVED", "REJECTED", "QA_FAILED"}:
            failures.append("archived_or_rejected")
            code = "ARCHIVED_AS_PRIMARY"
        role = (candidate.asset_role or "").upper()
        if role in REFERENCE_ROLES:
            failures.append("reference_as_primary")
            code = "REFERENCE_AS_PRIMARY"
        if previous_asset is None and previous_episode and previous_episode.primary_asset_id:
            previous_asset = _load_asset(previous_episode.primary_asset_id, store=store)
        same_id = bool(previous_asset and candidate.asset_id == previous_asset.asset_id)
        same_sha = bool(previous_asset and candidate.sha256 and candidate.sha256 == previous_asset.sha256)
        same_source = bool(previous_asset and candidate.source_asset_id and candidate.source_asset_id == previous_asset.asset_id and candidate.sha256 == previous_asset.sha256)
        same_package = bool(
            previous_episode
            and current_episode
            and previous_episode.content_package_id
            and previous_episode.content_package_id == current_episode.content_package_id
            and same_id
        )
        same_primary_role = bool(role in PRIMARY_ASSET_ROLES and (same_id or same_sha))
        reuse_ok = intent in REUSE_INTENTS or reuse_mode in REUSE_INTENTS
        if NEW_PRIMARY_ASSET_REQUIRED and intent in FRESHNESS_INTENTS and not reuse_ok:
            if same_sha or same_id or same_source or same_package or same_primary_role:
                failures.append("stale_asset_reuse")
                code = "STALE_ASSET_REUSE" if not same_sha else "SAME_FILE_REUSE"
        if candidate.account_id and account_id and candidate.account_id != account_id:
            failures.append("account_mismatch")
            code = code or "MISSING_ACCOUNT_SCOPE"
        if candidate.platform and platform and candidate.platform != platform and role in PRIMARY_ASSET_ROLES:
            failures.append("cross_platform_primary")
            code = "CROSS_PLATFORM_ASSET_REUSE"
        if not candidate.account_id or not candidate.platform:
            if role in PRIMARY_ASSET_ROLES or not role:
                failures.append("missing_account_scope")
                code = code or "MISSING_ACCOUNT_SCOPE"
        return {
            "decision": "FAIL" if failures else "PASS",
            "code": code,
            "failures": failures,
            "same_sha": same_sha,
            "same_asset_id": same_id,
            "same_source": same_source,
            "same_package": same_package,
            "same_primary_role": same_primary_role,
        }

    def assert_fresh(self, **kwargs: Any) -> dict[str, Any]:
        result = self.inspect(**kwargs)
        if result["decision"] == "FAIL":
            raise AssetFreshnessError(result.get("code") or "STALE_ASSET_REUSE", result.get("code") or "STALE_ASSET_REUSE")
        return result


class ReferenceAssetResolver:
    name = "reference_assets"

    def __init__(self, store: ContinuityStore | None = None) -> None:
        self.store = store or ContinuityStore()

    def resolve(
        self,
        *,
        account_id: str,
        platform: str,
        character_id: str | None = None,
        world_id: str | None = None,
        previous_episode: Episode | None = None,
        explicit: list[str] | tuple[str, ...] = (),
        allow_global: bool = True,
    ) -> list[MediaAsset]:
        refs: list[MediaAsset] = []
        seen: set[str] = set()
        for asset_id in explicit:
            asset = self._owned_or_global(
                asset_id,
                account_id=account_id,
                platform=platform,
                allow_global=allow_global,
                allow_cross_platform_reference=True,
            )
            if asset is not None:
                refs.append(asset)
                seen.add(asset.asset_id)
        if character_id:
            character = self.store.get_character(character_id, account_id=account_id)
            for asset_id in (character.reference_asset_ids if character else ()):
                if asset_id in seen:
                    continue
                asset = self._owned_or_global(asset_id, account_id=account_id, platform=platform, allow_global=allow_global)
                if asset is not None:
                    refs.append(asset)
                    seen.add(asset.asset_id)
        if previous_episode and previous_episode.primary_asset_id and previous_episode.primary_asset_id not in seen:
            previous = self._owned_or_global(
                previous_episode.primary_asset_id,
                account_id=account_id,
                platform=platform,
                allow_global=True,
                allow_cross_platform_reference=False,
            )
            if previous is not None:
                refs.append(previous)
        return refs

    def as_primary(self, asset: MediaAsset) -> None:
        raise AssetFreshnessError("REFERENCE_AS_PRIMARY", "reference asset cannot become primary")

    def _owned_or_global(
        self,
        asset_id: str,
        *,
        account_id: str,
        platform: str,
        allow_global: bool,
        allow_cross_platform_reference: bool = False,
    ) -> MediaAsset | None:
        asset = _load_asset(asset_id, store=self.store)
        if asset is None:
            return None
        if asset.account_id == account_id and (not asset.platform or asset.platform == platform):
            return asset
        if allow_global and (asset.scope_type or "").upper() == "GLOBAL":
            return asset
        if allow_cross_platform_reference and asset.platform and asset.platform != platform:
            role = (asset.asset_role or "").upper()
            if role in PRIMARY_ASSET_ROLES or not role:
                return replace(asset, asset_role="CHARACTER_REFERENCE")
            return asset
        return None


class PlatformAssetService:
    def __init__(self, store: ContinuityStore | None = None, creative=None) -> None:
        self.store = store or ContinuityStore()
        self.creative = creative
        self.freshness = AssetFreshnessGuard()
        self.references = ReferenceAssetResolver(self.store)
        self.qa = TechnicalQA()

    def ensure_pool(self, *, account_id: str, platform: str, character_id: str | None = None, world_id: str | None = None) -> PlatformAssetPool:
        existing = self.store.get_pool(account_id=account_id, platform=platform)
        if existing is not None:
            return existing
        return self.store.save_pool(PlatformAssetPool(
            pool_id=uuid4().hex,
            account_id=account_id,
            platform=platform,
            character_id=character_id,
            world_id=world_id,
        ))

    def list_assets(
        self,
        account_id: str,
        platform: str,
        role: str | None = None,
        episode_id: str | None = None,
        lifecycle: str | None = None,
        include_global: bool = True,
    ) -> list[MediaAsset]:
        return self.store.list_scoped_assets(
            account_id=account_id,
            platform=platform,
            role=role,
            episode_id=episode_id,
            lifecycle=lifecycle,
            include_global=include_global,
        )

    def import_asset(
        self,
        path: str | Path,
        *,
        account_id: str,
        platform: str,
        episode_id: str,
        asset_role: str,
        asset_type: str | None = None,
        reuse_mode: str = "NONE",
        intent: str = "GENERATE",
        parent_asset_id: str | None = None,
        source_asset_id: str | None = None,
        reference_asset_ids: tuple[str, ...] = (),
        prompt_id: str | None = None,
        model: str = "UNKNOWN",
        tool: str = "lechuang",
        generation_mode: str = "MANUAL_CREATIVE_TOOL",
        generation_timestamp: str | None = None,
        no_prompt_reference: bool = False,
        no_prompt_reason: str = "",
        operator: str = "operator",
        production_run_id: str | None = None,
        root: Path | None = None,
    ) -> dict[str, Any]:
        if asset_role not in ASSET_ROLES:
            raise ValueError(f"invalid asset_role: {asset_role}")
        if asset_role in PRIMARY_ASSET_ROLES and not prompt_id and not no_prompt_reference:
            raise ConfigurationBlocked(
                "NO_PROMPT_REFERENCE",
                "primary asset import requires prompt_id or explicit NO_PROMPT_REFERENCE",
            )
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        if account.platform != platform:
            raise IsolationError(f"account {account_id} is {account.platform}, not {platform}")
        episode = self.store.get_episode(episode_id, account_id=account_id)
        if episode is None:
            raise IsolationError(f"episode {episode_id} is not owned by {account_id}")
        if asset_role in PRIMARY_ASSET_ROLES and not prompt_id and no_prompt_reference:
            self.store.save_override(ManualOverride(
                override_id=uuid4().hex,
                account_id=account_id,
                platform=platform,
                target_kind="asset_import",
                target_id=episode_id,
                field_name="prompt_id",
                old_value=None,
                new_value="NO_PROMPT_REFERENCE",
                changed_by=operator,
                reason=no_prompt_reason or "explicit NO_PROMPT_REFERENCE",
                source="USER_OVERRIDE",
            ))
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(str(source))
        digest = sha256_file(source)
        existing = self.store.get_asset_by_sha256(digest)
        if existing is not None:
            raise ExistingAssetError("EXISTING_ASSET", self._existing_message(existing))
        pool = self.ensure_pool(account_id=account_id, platform=platform, character_id=account.character_id, world_id=account.world_id)
        kind = asset_type or _type_from_path(source)
        parent = parent_asset_id or source_asset_id
        if kind == "video" and (asset_role in PRIMARY_ASSET_ROLES) and source_asset_id:
            source_asset = _load_asset(source_asset_id, store=self.store)
            if source_asset is None:
                raise AssetFreshnessError("MISSING_SOURCE_ASSET", "IMAGE_TO_VIDEO requires source_asset_id")
            if source_asset.account_id not in {account_id, None} and (source_asset.scope_type or "").upper() != "GLOBAL":
                if source_asset.platform and source_asset.platform != platform:
                    parent = source_asset.asset_id
                    reuse_mode = "DERIVED" if reuse_mode == "NONE" else reuse_mode
        asset = persist_file(
            source,
            asset_type=kind,
            account_id=account_id,
            series_id=episode.series_id,
            episode_id=episode.episode_id,
            character_id=account.character_id,
            world_id=account.world_id,
            provider="manual-lechuang" if generation_mode == "MANUAL_CREATIVE_TOOL" else generation_mode,
            model=model or "UNKNOWN",
            prompt_id=prompt_id,
            metadata={
                "generation_timestamp": generation_timestamp or utcnow(),
                "tool": tool or "lechuang",
                "generation_mode": generation_mode,
            },
            platform=platform,
            scope_type="PLATFORM_ACCOUNT",
            asset_role=asset_role,
            lifecycle="IMPORTED",
            pool_id=pool.pool_id,
            parent_asset_id=parent,
            source_asset_id=source_asset_id or parent,
            generation_mode=generation_mode,
            tool=tool or "lechuang",
            **({"root": root} if root is not None else {}),
        )
        previous = self.store.get_episode(episode.previous_episode_id, account_id=account_id) if episode.previous_episode_id else None
        previous_asset = _load_asset(previous.primary_asset_id, store=self.store) if previous and previous.primary_asset_id else None
        if asset_role in PRIMARY_ASSET_ROLES:
            self.freshness.assert_fresh(
                current_episode=episode,
                candidate=asset,
                previous_episode=previous,
                previous_asset=previous_asset,
                platform=platform,
                account_id=account_id,
                intent=intent,
                reuse_mode=reuse_mode,
                store=self.store,
            )
            if previous_asset and asset.platform != previous_asset.platform and reuse_mode not in {"REFERENCE", "DERIVED", "NONE"}:
                raise CrossPlatformAssetReuse("CROSS_PLATFORM_ASSET_REUSE")
        saved = self._persist_asset(asset)
        qa = self.qa.inspect_video(saved) if saved.type == "video" else self.qa.inspect_image(saved)
        lifecycle = "QA_PASSED" if qa.get("decision") == "pass" else "QA_FAILED"
        measured = {
            "lifecycle": lifecycle,
            "width": qa.get("width") if qa.get("width") else saved.width,
            "height": qa.get("height") if qa.get("height") else saved.height,
            "mime_type": qa.get("mime") or saved.mime_type,
            "size": int(qa.get("filesize") or saved.size or 0),
            "duration": qa.get("duration") if qa.get("duration") is not None else saved.duration,
            "fps": qa.get("fps") if qa.get("fps") is not None else saved.fps,
        }
        saved = replace(saved, **measured)
        saved = self._persist_asset(saved)
        self.store.save_receipt(CreativeExecutionReceipt(
            receipt_id=uuid4().hex,
            asset_id=saved.asset_id,
            prompt_id=prompt_id,
            tool=tool or "lechuang",
            model=model or "UNKNOWN",
            operator=operator,
            source_asset_id=source_asset_id or parent,
            generation_mode=generation_mode,
            production_run_id=production_run_id or episode.production_run_id,
        ))
        self.store.save_evidence(ProductionEvidence(
            evidence_id=uuid4().hex,
            kind=f"DAY_{episode.episode_no:03d}_REAL_ASSET_IMPORTED",
            account_id=account_id,
            platform=platform,
            episode_id=episode.episode_id,
            prompt_id=prompt_id,
            asset_id=saved.asset_id,
            source="lechuang",
            detail={"sha256": saved.sha256, "qa": qa.get("decision"), "width": saved.width, "height": saved.height},
        ))
        origin_platform = ""
        origin_episode_id = None
        if parent:
            parent_asset = _load_asset(parent, store=self.store)
            if parent_asset is not None:
                origin_platform = parent_asset.platform or ""
                origin_episode_id = parent_asset.episode_id
                if origin_platform and origin_platform != platform and reuse_mode not in {"REFERENCE", "DERIVED"}:
                    raise CrossPlatformAssetReuse("CROSS_PLATFORM_ASSET_REUSE")
        lineage = AssetLineage(
            lineage_id=uuid4().hex,
            asset_id=saved.asset_id,
            account_id=account_id,
            series_id=episode.series_id,
            episode_id=episode.episode_id,
            character_id=account.character_id,
            world_id=account.world_id,
            user_request="manual-import",
            generation_request={
                "tool": tool or "lechuang",
                "model": model or "UNKNOWN",
                "prompt_id": prompt_id,
                "generation_timestamp": generation_timestamp or utcnow(),
                "generation_mode": generation_mode,
            },
            provider="manual-lechuang",
            model=model or "UNKNOWN",
            parent_asset_id=parent,
            source_asset_id=source_asset_id or parent,
            qa_decision=str(qa.get("decision") or ""),
            reference_asset_ids=tuple(reference_asset_ids),
            origin_episode_id=origin_episode_id,
            target_episode_id=episode.episode_id,
            origin_platform=origin_platform,
            target_platform=platform,
            reuse_mode=reuse_mode if reuse_mode != "NONE" or not parent else "DERIVED",
            generation_mode=generation_mode,
            tool=tool or "lechuang",
            prompt_id=prompt_id,
        )
        saved_lineage = self.store.allocate_attempt(
            account_id=account_id,
            episode_id=episode.episode_id,
            parent_asset_id=parent,
            lineage=lineage,
        )
        if asset_role in PRIMARY_ASSET_ROLES and lifecycle == "QA_PASSED":
            self.store.save_episode(Episode(**{**episode.__dict__, "primary_asset_id": saved.asset_id, "content_status": "QA_PASSED", "updated_at": utcnow()}))
        return {"asset": saved, "lineage": saved_lineage, "qa": qa, "status": "IMPORTED"}

    def map_package_asset(self, package: ContentPackage, asset: MediaAsset, *, role: str, selected: bool = False) -> ContentPackageAsset:
        if role not in PACKAGE_ASSET_ROLES:
            raise ValueError(f"invalid package asset role: {role}")
        if role == "PRIMARY":
            asset_role = str(getattr(asset, "asset_role", "") or "").upper()
            asset_platform = getattr(asset, "platform", "") or ""
            asset_account = getattr(asset, "account_id", None)
            if asset_role in REFERENCE_ROLES:
                raise AssetFreshnessError("REFERENCE_AS_PRIMARY", "reference asset cannot enter primary_assets")
            if asset_platform and package.platform and asset_platform != package.platform:
                raise CrossPlatformAssetReuse("CROSS_PLATFORM_ASSET_REUSE")
            if asset_account and package.account_id and asset_account != package.account_id:
                raise IsolationError("package primary asset must match account")
        mapping = ContentPackageAsset(
            mapping_id=uuid4().hex,
            package_id=package.package_id,
            asset_id=str(getattr(asset, "asset_id", "") or ""),
            role=role,
            selected=selected,
        )
        return self.store.save_package_asset(mapping)

    def _persist_asset(self, asset: MediaAsset) -> MediaAsset:
        if self.creative is not None:
            return self.creative.save_asset(asset)
        return self.store.save_media_asset(asset)

    def _existing_message(self, asset: MediaAsset) -> str:
        return (
            f"EXISTING_ASSET sha256={asset.sha256} asset_id={asset.asset_id} "
            f"account_id={asset.account_id or ''} platform={asset.platform or ''} "
            f"episode_id={asset.episode_id or ''}"
        )


def _type_from_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".mp4", ".mov", ".webm", ".mkv"}:
        return "video"
    if suffix in {".mp3", ".wav", ".aac", ".m4a"}:
        return "audio"
    return "image"


def _load_asset(asset_id: str | None, store: ContinuityStore | None = None) -> MediaAsset | None:
    if not asset_id:
        return None
    if store is not None:
        asset = store.get_media_asset(asset_id)
        if asset is not None:
            return asset
    from creative.store import CreativeStore
    return CreativeStore().get_asset(asset_id)
