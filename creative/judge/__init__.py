"""Judges return score/decision/reason. They never publish and never auto-PASS when blocked."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from creative.errors import JudgeBlocked, TechnicalMediaError
from creative.schemas import JudgeResult, MediaAsset, REGENERATION_STRATEGIES, utcnow

PASS_SCORE = 70.0


def _missing(judge_type: str) -> JudgeResult:
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
    )


class ImageJudge:
    name = "image"

    def __init__(self, provider=None) -> None:
        self.provider = provider

    def judge(self, asset: MediaAsset | None, *, context: dict[str, Any] | None = None, character=None, reference=None) -> JudgeResult:
        if asset is None:
            return _missing(self.name)
        if self.provider is None:
            raise JudgeBlocked("vision provider unavailable")
        return self.provider.judge_image(asset, brief=context or {}, character=character, reference=reference)


class VideoJudge:
    name = "video"

    def __init__(self, provider=None) -> None:
        self.provider = provider

    def judge(self, asset: MediaAsset | None, *, context: dict[str, Any] | None = None, character=None, reference=None) -> JudgeResult:
        if asset is None:
            return _missing(self.name)
        if self.provider is None:
            raise JudgeBlocked("vision provider unavailable")
        frames = []
        try:
            from creative.render.ffmpeg import extract_frames
            import tempfile
            with tempfile.TemporaryDirectory(prefix="meiti-judge-") as tmp:
                frames = extract_frames(asset.path, tmp)
                framed = self.provider.judge_frames(frames, brief=context or {}, character=character, reference=reference)
        except TechnicalMediaError:
            framed = None
        video = self.provider.judge_video(asset, brief=context or {}, character=character, reference=reference)
        if framed is None:
            return video
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
            breakdown={**dict(video.breakdown), **dict(framed.breakdown)},
            timestamp=utcnow(),
            asset_id=asset.asset_id,
            judge_id=uuid4().hex,
            judge_provider=video.judge_provider,
            creative_run_id=video.creative_run_id,
        )


class ConsistencyJudge:
    name = "consistency"

    def __init__(self, provider=None) -> None:
        self.provider = provider

    def judge(self, assets: list[MediaAsset], *, context: dict[str, Any] | None = None, character=None, reference=None) -> JudgeResult:
        if self.provider is None:
            raise JudgeBlocked("vision provider unavailable")
        return self.provider.judge_consistency(list(assets or []), brief=context or {}, character=character, reference=reference)


class PlatformFitJudge:
    name = "platform_fit"

    def __init__(self, provider=None) -> None:
        self.provider = provider

    def judge(self, asset: MediaAsset | None, *, context: dict[str, Any] | None = None, character=None, reference=None) -> JudgeResult:
        context = context or {}
        if asset is None:
            return _missing(self.name)
        breakdown = {"aspect_ratio": 80.0, "duration": 80.0, "safe_area": 80.0}
        reasons: list[str] = []
        wanted = str(context.get("aspect_ratio") or "9:16")
        if wanted == "9:16" and asset.width and asset.height and asset.width > asset.height:
            breakdown["aspect_ratio"] = 40.0
            reasons.append("fail: landscape asset for 9:16")
        score = sum(breakdown.values()) / len(breakdown)
        if any(item.startswith("fail:") for item in reasons):
            score = min(score, 40.0)
        return JudgeResult(
            score=round(score, 2),
            decision="PASS" if score >= PASS_SCORE and not reasons else "FAIL" if reasons else "PASS",
            reasons=tuple(reasons),
            judge_type=self.name,
            judge_model="policy",
            judge_version="v1",
            breakdown=breakdown,
            timestamp=utcnow(),
            asset_id=asset.asset_id,
            judge_id=uuid4().hex,
            judge_provider="policy",
        )


class ContentFitJudge:
    name = "content_fit"

    def __init__(self, provider=None) -> None:
        self.provider = provider

    def judge(self, asset: MediaAsset | None, *, context: dict[str, Any] | None = None, character=None, reference=None) -> JudgeResult:
        context = context or {}
        if asset is None:
            return _missing(self.name)
        breakdown = {"brief_alignment": 82.0, "commerce_restraint": 85.0}
        reasons: list[str] = []
        if context.get("commerce_intent") not in {None, "", "none"} and context.get("content_first", True) is False:
            breakdown["commerce_restraint"] = 50.0
            reasons.append("commerce intent without content-first brief")
        score = sum(breakdown.values()) / len(breakdown)
        return JudgeResult(
            score=round(score, 2),
            decision="PASS" if score >= PASS_SCORE else "FAIL",
            reasons=tuple(reasons),
            judge_type=self.name,
            judge_model="policy",
            judge_version="v1",
            breakdown=breakdown,
            timestamp=utcnow(),
            asset_id=asset.asset_id,
            judge_id=uuid4().hex,
            judge_provider="policy",
        )


class TechnicalQA:
    name = "technical"

    def inspect_image(self, asset: MediaAsset) -> dict[str, Any]:
        failures = []
        path = Path(asset.path) if asset.path else None
        if path is None or not path.is_file():
            return {"decision": "fail", "failures": ["missing_file"]}
        try:
            from PIL import Image
            with Image.open(path) as image:
                width, height = image.size
                fmt = (image.format or "").lower()
        except Exception:
            return {"decision": "fail", "failures": ["unreadable"]}
        mime = asset.mime_type or ""
        if mime and not mime.startswith("image/") and asset.type == "image":
            failures.append("format")
        if asset.size <= 0 and path.stat().st_size <= 0:
            failures.append("size")
        if width <= 0 or height <= 0:
            failures.append("resolution")
        return {
            "decision": "pass" if not failures else "fail",
            "failures": failures,
            "width": width,
            "height": height,
            "mime": mime or f"image/{fmt or 'png'}",
            "filesize": path.stat().st_size,
            "aspect_ratio": round(width / max(height, 1), 4),
        }

    def inspect_video(self, asset: MediaAsset) -> dict[str, Any]:
        failures = []
        path = Path(asset.path) if asset.path else None
        if path is None or not path.is_file():
            return {"decision": "fail", "failures": ["missing_file"]}
        try:
            from creative.render.ffmpeg import video_info
            info = video_info(path)
        except TechnicalMediaError:
            return {"decision": "fail", "failures": ["unreadable"]}
        if not info.get("codec"):
            failures.append("codec")
        if info.get("filesize", 0) <= 0:
            failures.append("file_size")
        if not info.get("width") or not info.get("height"):
            failures.append("resolution")
        return {
            "decision": "pass" if not failures else "fail",
            "failures": failures,
            **info,
        }


class RegenerationStrategy:
    def next_action(self, attempt: int, *, last: JudgeResult | None = None, max_regenerations: int | None = None) -> str:
        limit = max_regenerations if max_regenerations is not None else len(REGENERATION_STRATEGIES)
        if attempt >= limit:
            return "stop"
        if attempt >= len(REGENERATION_STRATEGIES):
            return "stop"
        return REGENERATION_STRATEGIES[attempt]


def rank_assets(pairs: list[tuple[MediaAsset, JudgeResult]]) -> list[tuple[MediaAsset, JudgeResult]]:
    return sorted(pairs, key=lambda item: item[1].score, reverse=True)


def bind_judges(provider=None) -> dict[str, Any]:
    return {
        "image": ImageJudge(provider),
        "video": VideoJudge(provider),
        "consistency": ConsistencyJudge(provider),
        "identity": ConsistencyJudge(provider),
        "platform_fit": PlatformFitJudge(provider),
        "content_fit": ContentFitJudge(provider),
        "continuity": ConsistencyJudge(provider),
    }


JUDGES = bind_judges()
