"""PromptCompiler is the human-execution creative bridge."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from content.dna import character_lock_prompt, default_creative_dna, merge_creative_dna, world_lock_prompt
from content.models import (
    AccountWorld,
    AssetFreshnessError,
    ContentSeries,
    CrossPlatformAssetReuse,
    Episode,
    IsolationError,
    MemoryWritebackError,
    PRIMARY_ASSET_ROLES,
    PlatformCreativeDNA,
    PromptPackage,
    PromptPattern,
    VirtualCharacter,
    utcnow,
)
from content.platform_policy import platform_policy
from content.store import ContinuityStore


NEGATIVE_BASE = (
    "beauty filter, plastic skin, extra fingers, watermark, logo lockup, "
    "stock-photo posing, identical previous-episode still reused as new primary"
)


class PromptCompiler:
    def __init__(self, store: ContinuityStore | None = None) -> None:
        self.store = store or ContinuityStore()

    def compile(
        self,
        *,
        account_id: str,
        platform: str,
        request: str,
        kind: str | None = None,
        character: VirtualCharacter | None = None,
        world: AccountWorld | None = None,
        series: ContentSeries | None = None,
        episode: Episode | None = None,
        previous: Episode | None = None,
        previous_prompt: PromptPackage | None = None,
        dna: PlatformCreativeDNA | None = None,
        continuity: dict[str, Any] | None = None,
        learning: dict[str, Any] | None = None,
        reference_assets: list[Any] | tuple[Any, ...] = (),
        source_assets: list[Any] | tuple[Any, ...] = (),
        source_asset_id: str | None = None,
        intent: str = "GENERATE",
    ) -> PromptPackage:
        account = self.store.get_account(account_id)
        if account is None:
            raise ValueError(f"unknown platform account: {account_id}")
        if account.platform != platform:
            raise ValueError(f"account {account_id} is {account.platform}, not {platform}")
        policy = platform_policy(platform)
        dna = merge_creative_dna(account_id, platform, dna or self.store.get_creative_dna(account_id, platform))
        self.store.save_creative_dna(dna)
        kind = (kind or _kind_from_policy(policy, request, source_asset_id)).upper()
        if kind == "IMAGE_TO_VIDEO" and not source_asset_id and not source_assets:
            raise AssetFreshnessError("MISSING_SOURCE_ASSET", "IMAGE_TO_VIDEO requires source_asset_id")
        character_lock = character_lock_prompt(character)
        world_lock = world_lock_prompt(world)
        scene = _scene_prompt(request=request, episode=episode, previous=previous, continuity=continuity, kind=kind, dna=dna)
        if previous_prompt is None and previous is not None and previous.prompt_id:
            previous_prompt = self.store.get_prompt(previous.prompt_id)
        if previous_prompt and scene.strip() == (previous_prompt.scene_prompt or "").strip() and intent not in {"REUSE", "REPUBLISH"}:
            raise AssetFreshnessError("DUPLICATE_CONTENT", "scene prompt cannot copy the previous episode")
        patterns = self.store.list_prompt_patterns(platform=platform, account_id=account_id)
        pattern_ids = tuple(item.pattern_id for item in patterns[:8])
        learning_basis = _learning_basis(learning or {}, platform=platform)
        refs = self._validate_references(
            tuple(_asset_id(item) for item in reference_assets if _asset_id(item)),
            account_id=account_id,
            platform=platform,
        )
        sources = tuple(_asset_id(item) for item in source_assets if _asset_id(item))
        if source_asset_id and source_asset_id not in sources:
            sources = (source_asset_id,) + sources
        prompt_dna = dict(dna.prompt_dna or {})
        visual = _join_map(dna.visual_style) or str(prompt_dna.get("look") or "")
        camera = dna.camera_style
        motion = dna.motion_style
        lighting = str((world.visual_language or {}).get("light") if world else "") or str((dna.visual_style or {}).get("grade") or "")
        composition = str(prompt_dna.get("composition") or "")
        authenticity = str(prompt_dna.get("authenticity") or "")
        negative = "; ".join(part for part in (NEGATIVE_BASE, prompt_dna.get("negative"), *(world.taboos if world else ())) if part)
        ratio = str(policy.get("aspect_ratio") or ("3:4" if kind == "IMAGE" else "9:16"))
        duration = "0" if kind == "IMAGE" else str((dna.prompt_dna or {}).get("duration") or "6")
        model = "gpt-image-2" if kind == "IMAGE" else "lechuang-manual-video"
        size = "2K" if kind == "IMAGE" else ""
        copy_ready = _copy_ready(
            kind=kind,
            character_lock=character_lock,
            world_lock=world_lock,
            scene=scene,
            composition=composition,
            camera=camera,
            motion=motion,
            lighting=lighting,
            visual=visual,
            authenticity=authenticity,
            negative=negative,
            ratio=ratio,
            duration=duration,
            source_asset_id=source_asset_id,
            references=refs,
            dna=dna,
            lens=_lens_for(platform, kind),
        )
        package = PromptPackage(
            prompt_id=uuid4().hex,
            account_id=account_id,
            platform=platform,
            kind=kind,
            character_id=character.character_id if character else None,
            world_id=world.world_id if world else None,
            series_id=series.series_id if series else None,
            episode_id=episode.episode_id if episode else None,
            character_lock=character_lock,
            world_lock=world_lock,
            scene_prompt=scene,
            visual_style=visual,
            camera=camera,
            motion=motion,
            composition=composition,
            lighting=lighting,
            negative_prompt=negative,
            lens=_lens_for(platform, kind),
            material_texture="real fabric, real skin, real surfaces",
            authenticity=authenticity,
            shot_list=_shot_list(kind, scene, dna),
            temporal_sequence=_temporal(kind, scene),
            camera_movement=camera if kind != "IMAGE" else "",
            character_motion=motion if kind != "IMAGE" else "",
            environment_motion="ambient air and background life" if kind != "IMAGE" else "",
            start_state=_start_state(previous, scene) if kind != "IMAGE" else "",
            end_state=_end_state(scene) if kind != "IMAGE" else "",
            duration=duration,
            aspect_ratio=ratio,
            copy_ready=copy_ready,
            reference_assets=refs,
            source_assets=sources,
            source_asset_id=source_asset_id,
            recommended_model=model,
            recommended_size=size,
            recommended_ratio=ratio,
            recommended_duration=duration,
            learning_basis=learning_basis,
            prompt_patterns=pattern_ids,
            parent_prompt_id=previous_prompt.prompt_id if previous_prompt else None,
            version=(previous_prompt.version + 1) if previous_prompt else 1,
            lechuang_parameters={
                "tool": "lechuang",
                "mode": "manual",
                "model": model,
                "size": size,
                "aspect_ratio": ratio,
                "duration": duration,
            },
        )
        if previous_prompt and intent not in {"REUSE", "REPUBLISH"}:
            if package.copy_ready.strip() == (previous_prompt.copy_ready or "").strip():
                raise AssetFreshnessError("DUPLICATE_CONTENT", "copy_ready prompt cannot copy the previous episode")
        saved = self.store.save_prompt(package)
        if episode is not None:
            self.store.save_episode(Episode(**{
                **episode.__dict__,
                "prompt_id": saved.prompt_id,
                "character_revision": character.version if character else episode.character_revision,
                "world_revision": world.version if world else episode.world_revision,
                "updated_at": utcnow(),
            }))
        self._project(saved)
        return saved

    def _validate_references(self, refs: tuple[str, ...], *, account_id: str, platform: str) -> tuple[str, ...]:
        from content.assets import ReferenceAssetResolver

        resolver = ReferenceAssetResolver(self.store)
        resolved = resolver.resolve(
            account_id=account_id,
            platform=platform,
            explicit=refs,
            allow_global=True,
        )
        by_id = {item.asset_id: item for item in resolved}
        validated: list[str] = []
        for asset_id in refs:
            asset = by_id.get(asset_id)
            if asset is None:
                raise IsolationError(f"reference asset {asset_id} is not owned by {account_id}", code="REFERENCE_SCOPE_MISMATCH")
            role = (asset.asset_role or "").upper()
            if role in PRIMARY_ASSET_ROLES and asset.platform and asset.platform != platform:
                raise CrossPlatformAssetReuse("CROSS_PLATFORM_ASSET_REUSE")
            lifecycle = (asset.lifecycle or "").upper()
            if lifecycle in {"ARCHIVED", "REJECTED", "QA_FAILED"}:
                raise AssetFreshnessError("STALE_REFERENCE", f"reference asset {asset_id} lifecycle is {lifecycle}")
            validated.append(asset.asset_id)
        return tuple(validated)

    def _project(self, package: PromptPackage) -> None:
        try:
            from memory.service import get_memory_service
            get_memory_service().remember(
                title=f"Prompt {package.kind} {package.prompt_id[:8]}",
                content=package.copy_ready or package.scene_prompt,
                scope_type="EPISODE",
                account_id=package.account_id,
                platform=package.platform,
                series_id=package.series_id,
                episode_id=package.episode_id,
                character_id=package.character_id,
                world_id=package.world_id,
                source_type="creative",
                tags=("PROMPT", package.kind, package.platform),
                document_id=f"prompt-{package.prompt_id}",
            )
        except Exception:
            return


def _kind_from_policy(policy: dict[str, Any], request: str, source_asset_id: str | None) -> str:
    if source_asset_id or "图生视频" in request or "image-to-video" in request.lower() or "i2v" in request.lower():
        return "IMAGE_TO_VIDEO"
    media = tuple(policy.get("media") or ())
    if "video" in media or any(token in request for token in ("视频", "video")):
        return "VIDEO"
    return "IMAGE"


def _scene_prompt(*, request: str, episode: Episode | None, previous: Episode | None, continuity: dict[str, Any] | None, kind: str, dna: PlatformCreativeDNA) -> str:
    brief = (episode.brief if episode else "") or request
    location = ""
    if episode and episode.location_state:
        location = str(episode.location_state.get("name") or episode.location_state.get("place") or "")
    previous_title = ""
    if previous:
        previous_title = previous.title
    elif continuity:
        previous_title = str(continuity.get("previous_title") or "")
    parts = [brief.strip()]
    if location:
        parts.append(f"Scene location: {location}.")
    if previous_title:
        parts.append(f"Continue the story after: {previous_title}. Do not reuse that episode's primary media.")
    parts.append(f"Emotion: {dna.emotion_style}." if dna.emotion_style else "")
    parts.append(f"Audience relationship: {dna.audience_relationship}." if dna.audience_relationship else "")
    if kind != "IMAGE":
        parts.append("This is a new moving scene, not yesterday's still.")
    else:
        parts.append("This is a new still for this episode, not a republish of an old image.")
    scene = " ".join(part for part in parts if part).strip()
    return _novel_scene(scene, episode=episode, request=request, platform=dna.platform)


def _novel_scene(scene: str, *, episode: Episode | None, request: str, platform: str) -> str:
    marker = episode.title if episode and episode.title else request[:40]
    return f"{scene} New episode beat for {platform}: {marker}.".strip()


def _learning_basis(learning: dict[str, Any], *, platform: str) -> tuple[str, ...]:
    rows = []
    for key in ("successful_patterns", "failed_patterns", "prompt_patterns", "high_performance_hooks", "high_performance_visuals"):
        for item in learning.get(key) or ():
            text = getattr(item, "title", None) or str(item)
            item_platform = getattr(item, "platform", None) or (item.get("platform") if isinstance(item, dict) else "")
            if item_platform and item_platform not in {platform, "GLOBAL", ""}:
                continue
            rows.append(str(text))
    for item in learning.get("learning_records") or ():
        if not isinstance(item, dict):
            continue
        if item.get("evidence_status") and item.get("evidence_status") != "VERIFIED":
            continue
        if item.get("platform") and item.get("platform") not in {platform, "GLOBAL", ""}:
            continue
        reason = item.get("reason") or item.get("next_recommendation") or item.get("what_worked") or ""
        if reason:
            rows.append(str(reason))
    return tuple(list(dict.fromkeys(rows))[:12])


def _asset_id(item: Any) -> str:
    if item is None:
        return ""
    return str(getattr(item, "asset_id", None) or item)


def _join_map(value: dict[str, Any] | None) -> str:
    if not value:
        return ""
    return ", ".join(f"{key}={item}" for key, item in value.items() if item)


def _lens_for(platform: str, kind: str) -> str:
    if platform == "xiaohongshu":
        return "smartphone wide, 24-28mm equivalent"
    if kind == "IMAGE":
        return "35mm equivalent"
    return "handheld 24mm vertical"


def _shot_list(kind: str, scene: str, dna: PlatformCreativeDNA) -> tuple[str, ...]:
    if kind == "IMAGE":
        return ()
    return (
        f"Hook ({dna.hook_style or 'open'}): {scene[:80]}",
        f"Motion: {dna.motion_style or 'keep the body moving'}",
        f"Hold: {dna.camera_style or 'hold framing'}",
    )


def _temporal(kind: str, scene: str) -> str:
    if kind == "IMAGE":
        return ""
    return f"Start already in action. Mid: {scene[:80]}. End on a still-readable beat."


def _start_state(previous: Episode | None, scene: str) -> str:
    if previous:
        return f"After {previous.title or 'the previous episode'}, begin a new action."
    return f"Begin already inside: {scene[:80]}"


def _end_state(scene: str) -> str:
    return "End on a new frame that is not the source still."


def _copy_ready(
    *,
    kind: str,
    character_lock: str,
    world_lock: str,
    scene: str,
    composition: str,
    camera: str,
    motion: str,
    lighting: str,
    visual: str,
    authenticity: str,
    negative: str,
    ratio: str,
    duration: str,
    source_asset_id: str | None,
    references: tuple[str, ...],
    dna: PlatformCreativeDNA,
    lens: str,
) -> str:
    header = {
        "IMAGE": "IMAGE PROMPT PACKAGE",
        "VIDEO": "VIDEO PROMPT PACKAGE",
        "IMAGE_TO_VIDEO": "IMAGE_TO_VIDEO PACKAGE",
    }[kind]
    lines = [
        "COPY READY",
        header,
        "",
        character_lock,
        "",
        world_lock,
        "",
        "SCENE",
        scene,
    ]
    if kind == "IMAGE":
        lines.extend([
            "",
            "COMPOSITION",
            composition,
            "CAMERA",
            camera,
            "LENS",
            lens,
            "LIGHTING",
            lighting,
            "STYLE",
            visual,
            "MATERIAL/TEXTURE",
            "real fabric, real skin, real surfaces",
            "AUTHENTICITY",
            authenticity,
        ])
    else:
        lines.extend([
            "",
            "SHOT LIST",
            "\n".join(_shot_list(kind, scene, dna)),
            "TEMPORAL SEQUENCE",
            _temporal(kind, scene),
            "CAMERA MOVEMENT",
            camera,
            "CHARACTER MOTION",
            motion,
            "ENVIRONMENT MOTION",
            "ambient air and background life",
            "LIGHTING",
            lighting,
            "STYLE",
            visual,
            "AUTHENTICITY",
            authenticity,
            "DURATION",
            duration,
            "ASPECT_RATIO",
            ratio,
        ])
    if kind == "IMAGE_TO_VIDEO":
        lines.extend([
            "",
            "SOURCE IMAGE",
            "input/reference only; output must be a new video asset",
            "SOURCE ASSET ID",
            source_asset_id or "",
            "START STATE",
            "begin from the source still without publishing the still",
            "END STATE",
            "end on a new frame",
        ])
    lines.extend(["", "NEGATIVE PROMPT", negative, "", "LECHUANG PARAMETERS", f"tool=lechuang mode=manual aspect_ratio={ratio} duration={duration}"])
    if references:
        lines.extend(["", "REFERENCE ASSETS", ", ".join(references)])
    return "\n".join(lines)
