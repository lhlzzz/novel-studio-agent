"""Video judge extracts frames, then vision + temporal checks."""

from __future__ import annotations

import tempfile
from typing import Any
from uuid import uuid4

from creative.errors import JudgeBlocked, TechnicalMediaError
from creative.judges.vision import missing_asset
from creative.schemas import JudgeResult, MediaAsset, utcnow

PASS_SCORE = 70.0


class VideoJudge:
    name = "video"

    def __init__(self, provider=None) -> None:
        self.provider = provider

    def judge(self, asset: MediaAsset | None, *, context: dict[str, Any] | None = None, character=None, reference=None) -> JudgeResult:
        if asset is None:
            return missing_asset(self.name)
        if self.provider is None:
            raise JudgeBlocked("vision provider unavailable")
        frames = []
        framed = None
        try:
            from creative.render.ffmpeg import extract_frames
            with tempfile.TemporaryDirectory(prefix="meiti-judge-") as tmp:
                frames = extract_frames(asset.path, tmp)
                framed = self.provider.judge_frames(frames, brief=context or {}, character=character, reference=reference)
        except TechnicalMediaError:
            framed = None
        video = self.provider.judge_video(asset, brief=context or {}, character=character, reference=reference)
        if framed is None:
            if getattr(self.provider, "name", "") == "mock-vision" and asset.path:
                framed = self.provider.judge_frames([asset.path], brief=context or {}, character=character, reference=reference)
            else:
                raise JudgeBlocked("video frame analysis unavailable")
        score = min(video.score, framed.score)
        reasons = tuple(dict.fromkeys([*video.reasons, *framed.reasons]))
        decision = "PASS" if score >= PASS_SCORE and not any(item.startswith("fail:") for item in reasons) else "FAIL"
        return JudgeResult(
            score=round(score, 2),
            decision=decision,
            reasons=reasons,
            judge_type=self.name,
            judge_model=video.judge_model,
            judge_version=video.judge_version,
            breakdown={**dict(video.breakdown), **dict(framed.breakdown), "temporal": framed.score, "frame_count": float(len(frames))},
            timestamp=utcnow(),
            asset_id=asset.asset_id,
            judge_id=uuid4().hex,
            judge_provider=video.judge_provider,
            creative_run_id=video.creative_run_id,
            passed=decision == "PASS",
            violations=tuple(item for item in reasons if item.startswith("fail:")),
            warnings=tuple(item for item in reasons if not item.startswith("fail:")),
            latency_ms=float(getattr(video, "latency_ms", 0) or 0) + float(getattr(framed, "latency_ms", 0) or 0),
            cost=getattr(video, "cost", None),
        )
