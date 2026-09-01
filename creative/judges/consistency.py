"""Identity / continuity judge. Requires vision provider."""

from __future__ import annotations

from typing import Any

from creative.errors import JudgeBlocked
from creative.schemas import JudgeResult, MediaAsset


class ConsistencyJudge:
    name = "consistency"

    def __init__(self, provider=None) -> None:
        self.provider = provider

    def judge(self, assets: list[MediaAsset], *, context: dict[str, Any] | None = None, character=None, reference=None) -> JudgeResult:
        if self.provider is None:
            raise JudgeBlocked("vision provider unavailable")
        return self.provider.judge_consistency(list(assets or []), brief=context or {}, character=character, reference=reference)
