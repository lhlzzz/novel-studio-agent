"""Immutable MediaAsset and Character storage keyed by sha256."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Any, Callable

from creative.schemas import ASSET_TYPES, Character, MediaAsset, VisualDNA

MIN_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "media" / "assets"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def persist_bytes(
    data: bytes,
    *,
    asset_type: str,
    suffix: str,
    root: Path | None = None,
    mime_type: str = "",
    width: int | None = None,
    height: int | None = None,
    duration: float | None = None,
    fps: float | None = None,
    workflow_id: str | None = None,
    workflow_version: str | None = None,
    creative_run_id: str | None = None,
    prompt_id: str | None = None,
    character_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    account_id: str | None = None,
    series_id: str | None = None,
    episode_id: str | None = None,
    content_package_id: str | None = None,
    creative_context_id: str | None = None,
    world_id: str | None = None,
    provider: str = "",
    provider_task_id: str = "",
    model: str = "",
    platform: str = "",
    scope_type: str = "PLATFORM_ACCOUNT",
    asset_role: str = "",
    lifecycle: str = "DRAFT",
    pool_id: str | None = None,
    parent_asset_id: str | None = None,
    source_asset_id: str | None = None,
    generation_mode: str = "",
    tool: str = "",
) -> MediaAsset:
    if asset_type not in ASSET_TYPES:
        raise ValueError(asset_type)
    root = Path(root or DEFAULT_ROOT)
    digest = sha256_bytes(data)
    dest_dir = root / digest[:2]
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    dest = dest_dir / f"{digest}{suffix}"
    if not dest.exists():
        dest.write_bytes(data)
    mime = mime_type or (mimetypes.guess_type(dest.name)[0] or "application/octet-stream")
    return MediaAsset(
        asset_id=digest,
        type=asset_type,
        path=str(dest),
        sha256=digest,
        width=width,
        height=height,
        duration=duration,
        fps=fps,
        mime_type=mime,
        workflow_id=workflow_id,
        workflow_version=workflow_version,
        creative_run_id=creative_run_id,
        prompt_id=prompt_id,
        character_id=character_id,
        size=len(data),
        metadata=dict(metadata or {}),
        account_id=account_id,
        series_id=series_id,
        episode_id=episode_id,
        content_package_id=content_package_id,
        creative_context_id=creative_context_id,
        world_id=world_id,
        provider=provider,
        provider_task_id=provider_task_id,
        model=model,
        platform=platform,
        scope_type=scope_type,
        asset_role=asset_role,
        lifecycle=lifecycle,
        pool_id=pool_id,
        parent_asset_id=parent_asset_id,
        source_asset_id=source_asset_id,
        generation_mode=generation_mode,
        tool=tool,
    )


def persist_file(path: Path, *, asset_type: str, **fields: Any) -> MediaAsset:
    data = Path(path).read_bytes()
    suffix = Path(path).suffix or ".bin"
    return persist_bytes(data, asset_type=asset_type, suffix=suffix, **fields)


class AssetStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or DEFAULT_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)
        self.assets: dict[str, MediaAsset] = {}
        self.characters: dict[str, Character] = {}
        self._persist_asset: Callable[[MediaAsset], MediaAsset] | None = None
        self._persist_character: Callable[[Character], Character] | None = None
        self._load_character: Callable[[str], Character | None] | None = None

    def put(self, asset: MediaAsset, *, persist: bool = True) -> MediaAsset:
        existing = self.assets.get(asset.sha256)
        canonical = existing or asset
        if persist and self._persist_asset is not None and existing is None:
            canonical = self._persist_asset(canonical) or canonical
        self.assets[canonical.sha256] = canonical
        self.assets[canonical.asset_id] = canonical
        if asset.asset_id != canonical.asset_id:
            self.assets[asset.asset_id] = canonical
        return canonical

    def get(self, asset_id: str) -> MediaAsset | None:
        return self.assets.get(asset_id)

    def put_character(self, character: Character) -> Character:
        self.characters[character.character_id] = character
        if self._persist_character is not None:
            return self._persist_character(character)
        return character

    def get_character(self, character_id: str) -> Character | None:
        cached = self.characters.get(character_id)
        if cached is not None:
            return cached
        if self._load_character is not None:
            loaded = self._load_character(character_id)
            if loaded is not None:
                self.characters[character_id] = loaded
            return loaded
        return None

    def save_generated(
        self,
        data: bytes,
        *,
        asset_type: str,
        suffix: str,
        **fields: Any,
    ) -> MediaAsset:
        asset = persist_bytes(data, asset_type=asset_type, suffix=suffix, root=self.root, **fields)
        return self.put(asset)


def character_from_dict(data: dict[str, Any]) -> Character:
    dna = data.get("visual_dna") or {}
    return Character(
        character_id=str(data["character_id"]),
        name=str(data.get("name") or data["character_id"]),
        visual_dna=VisualDNA(**{key: str(dna.get(key) or "") for key in VisualDNA.__dataclass_fields__}),
        behavior_dna=str(data.get("behavior_dna") or ""),
        style_dna=str(data.get("style_dna") or ""),
        reference_assets=tuple(data.get("reference_assets") or ()),
        voice_assets=tuple(data.get("voice_assets") or ()),
        notes=str(data.get("notes") or ""),
    )


def media_asset_from_dict(data: dict[str, Any]) -> MediaAsset:
    return MediaAsset(
        asset_id=str(data["asset_id"]),
        type=str(data.get("type") or "image"),
        path=str(data.get("path") or ""),
        sha256=str(data.get("sha256") or data["asset_id"]),
        width=data.get("width"),
        height=data.get("height"),
        duration=data.get("duration"),
        fps=data.get("fps"),
        mime_type=str(data.get("mime_type") or ""),
        workflow_id=data.get("workflow_id"),
        workflow_version=data.get("workflow_version"),
        creative_run_id=data.get("creative_run_id"),
        prompt_id=data.get("prompt_id"),
        character_id=data.get("character_id"),
        size=int(data.get("size") or 0),
        metadata=dict(data.get("metadata") or {}),
        account_id=data.get("account_id"),
        series_id=data.get("series_id"),
        episode_id=data.get("episode_id"),
        content_package_id=data.get("content_package_id"),
        creative_context_id=data.get("creative_context_id"),
        world_id=data.get("world_id"),
        provider=str(data.get("provider") or ""),
        provider_task_id=str(data.get("provider_task_id") or ""),
        model=str(data.get("model") or ""),
        platform=str(data.get("platform") or ""),
        scope_type=str(data.get("scope_type") or "PLATFORM_ACCOUNT"),
        asset_role=str(data.get("asset_role") or ""),
        lifecycle=str(data.get("lifecycle") or "DRAFT"),
        pool_id=data.get("pool_id"),
        parent_asset_id=data.get("parent_asset_id"),
        source_asset_id=data.get("source_asset_id"),
        generation_mode=str(data.get("generation_mode") or ""),
        tool=str(data.get("tool") or ""),
        technical_score=data.get("technical_score"),
        visual_score=data.get("visual_score"),
        content_score=data.get("content_score"),
        platform_score=data.get("platform_score"),
        overall_score=data.get("overall_score"),
    )
