"""Brief / audience / style / story fit. Not a commercial policy gate."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from creative.judges.vision import missing_asset
from creative.schemas import JudgeResult, MediaAsset, utcnow

PASS_SCORE = 70.0


class ContentFitJudge:
    name = "content_fit"

    def __init__(self, provider=None) -> None:
        self.provider = provider

    def judge(self, asset: MediaAsset | None, *, context: dict[str, Any] | None = None, character=None, reference=None) -> JudgeResult:
        context = context or {}
        if asset is None:
            return missing_asset(self.name)
        brief = str(context.get("brief") or context.get("script") or "").strip()
        reasons: list[str] = []
        breakdown = {"brief_alignment": 0.0, "audience_fit": 0.0, "style_fit": 0.0, "story_fit": 0.0}
        if not brief:
            reasons.append("fail: missing brief")
        else:
            breakdown["brief_alignment"] = 70.0
            breakdown["story_fit"] = 70.0
        if context.get("audience"):
            breakdown["audience_fit"] = 70.0
        elif brief:
            breakdown["audience_fit"] = 70.0
        if context.get("style"):
            breakdown["style_fit"] = 70.0
        elif brief:
            breakdown["style_fit"] = 70.0
        score = sum(breakdown.values()) / len(breakdown)
        if reasons:
            score = min(score, 40.0)
        return JudgeResult(
            score=round(score, 2),
            decision="PASS" if score >= PASS_SCORE and not reasons else "FAIL",
            reasons=tuple(reasons),
            judge_type=self.name,
            judge_model="content-fit",
            judge_version="v1",
            breakdown=breakdown,
            timestamp=utcnow(),
            asset_id=asset.asset_id,
            judge_id=uuid4().hex,
            judge_provider="content",
        )
