"""Optional derived media for platform constraints. Original MediaAsset is never mutated."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DerivedAsset:
    source_asset_id: str
    target_platform: str
    transformation: str
    derived_asset_id: str


def prepare_derived_asset(*, source_asset_id: str, target_platform: str, transformation: str, derived_asset_id: str) -> DerivedAsset:
    return DerivedAsset(
        source_asset_id=source_asset_id,
        target_platform=target_platform,
        transformation=transformation,
        derived_asset_id=derived_asset_id,
    )
