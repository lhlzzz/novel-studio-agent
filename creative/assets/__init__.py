"""Immutable MediaAsset and Character storage keyed by sha256."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Any
from uuid import uuid4

from creative.schemas import ASSET_TYPES, Character, MediaAsset, VisualDNA, utcnow

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
    character_id: str | None = None,
    metadata: dict[str, Any] | None = None,
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
        character_id=character_id,
        size=len(data),
        metadata=dict(metadata or {}),
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

    def put(self, asset: MediaAsset) -> MediaAsset:
        existing = self.assets.get(asset.sha256)
        canonical = existing or asset
        self.assets[canonical.sha256] = canonical
        self.assets[canonical.asset_id] = canonical
        self.assets[asset.asset_id] = asset if asset.asset_id != canonical.asset_id else canonical
        return canonical

    def get(self, asset_id: str) -> MediaAsset | None:
        return self.assets.get(asset_id)

    def put_character(self, character: Character) -> Character:
        self.characters[character.character_id] = character
        return character

    def get_character(self, character_id: str) -> Character | None:
        return self.characters.get(character_id)

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


def new_placeholder_id() -> str:
    return uuid4().hex
