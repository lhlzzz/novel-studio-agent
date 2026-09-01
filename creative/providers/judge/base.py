"""Vision judge provider contract. Judges never publish."""

from __future__ import annotations

from typing import Any, Protocol

from creative.schemas import Character, JudgeResult, MediaAsset


class VisionJudgeProvider(Protocol):
    name: str

    def live_ready(self) -> tuple[bool, str]: ...
    def judge_image(self, asset: MediaAsset, *, brief: dict[str, Any] | None = None, character: Character | None = None, reference: MediaAsset | None = None) -> JudgeResult: ...
    def judge_video(self, asset: MediaAsset, *, brief: dict[str, Any] | None = None, character: Character | None = None, reference: MediaAsset | None = None) -> JudgeResult: ...
    def judge_frames(self, frames: list[str], *, brief: dict[str, Any] | None = None, character: Character | None = None, reference: MediaAsset | None = None) -> JudgeResult: ...
    def judge_consistency(self, assets: list[MediaAsset], *, brief: dict[str, Any] | None = None, character: Character | None = None, reference: MediaAsset | None = None) -> JudgeResult: ...
