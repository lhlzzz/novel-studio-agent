"""Vision judge. Requires a real vision provider; never auto-scores."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from creative.errors import JudgeBlocked
from creative.schemas import JudgeResult, MediaAsset, utcnow


def missing_asset(judge_type: str) -> JudgeResult:
    return JudgeResult(
        score=0.0,
        decision="FAIL",
        reasons=("fail: missing asset",),
        judge_type=judge_type,
        judge_model="",
        judge_version="v1",
        breakdown={},
        timestamp=utcnow(),
        judge_id=uuid4().hex,
        judge_provider="",
        passed=False,
        violations=("fail: missing asset",),
    )


class ImageJudge:
    name = "image"

    def __init__(self, provider=None) -> None:
        self.provider = provider

    def judge(self, asset: MediaAsset | None, *, context: dict[str, Any] | None = None, character=None, reference=None) -> JudgeResult:
        if asset is None:
            return missing_asset(self.name)
        if self.provider is None:
            raise JudgeBlocked("vision provider unavailable")
        return self.provider.judge_image(asset, brief=context or {}, character=character, reference=reference)
