"""Judges return score/decision/reason. They never publish."""

from __future__ import annotations

from typing import Any

from creative.schemas import JudgeResult, MediaAsset, REGENERATION_STRATEGIES, utcnow

PASS_SCORE = 70.0


def _result(*, score: float, reasons: list[str], judge_type: str, breakdown: dict[str, float], asset_id: str | None = None, version: str = "heuristic-v1") -> JudgeResult:
    decision = "PASS" if score >= PASS_SCORE and not any(item.startswith("fail:") for item in reasons) else "FAIL"
    return JudgeResult(
        score=round(score, 2),
        decision=decision,
        reasons=tuple(reasons),
        judge_type=judge_type,
        judge_model="heuristic",
        judge_version=version,
        breakdown=breakdown,
        timestamp=utcnow(),
        asset_id=asset_id,
    )


class ImageJudge:
    name = "image"

    def judge(self, asset: MediaAsset | None, *, context: dict[str, Any] | None = None) -> JudgeResult:
        context = context or {}
        reasons: list[str] = []
        breakdown = {
            "composition": 80.0,
            "face_quality": 80.0,
            "identity_consistency": 80.0,
            "artifact_score": 80.0,
            "lighting": 80.0,
            "aesthetic": 80.0,
            "content_fit": 80.0,
        }
        if asset is None or not asset.path:
            return _result(score=0, reasons=["fail: missing image asset"], judge_type=self.name, breakdown={key: 0.0 for key in breakdown})
        if asset.type not in {"image", "reference", "final"}:
            reasons.append("fail: not an image")
            breakdown["composition"] = 20.0
        if asset.width and asset.height:
            ratio = asset.width / max(asset.height, 1)
            wanted = str(context.get("aspect_ratio") or "")
            if wanted == "9:16" and ratio > 0.7:
                breakdown["composition"] = 60.0
                reasons.append("aspect ratio drifts from 9:16")
        if context.get("character_id") and asset.character_id and asset.character_id != context.get("character_id"):
            breakdown["identity_consistency"] = 40.0
            reasons.append("fail: identity mismatch")
        if context.get("face_visible") is False:
            breakdown["face_quality"] = 88.0
        score = sum(breakdown.values()) / len(breakdown)
        if reasons and any(item.startswith("fail:") for item in reasons):
            score = min(score, 40.0)
        return _result(score=score, reasons=reasons, judge_type=self.name, breakdown=breakdown, asset_id=asset.asset_id)


class VideoJudge:
    name = "video"

    def judge(self, asset: MediaAsset | None, *, context: dict[str, Any] | None = None) -> JudgeResult:
        context = context or {}
        reasons: list[str] = []
        breakdown = {
            "motion_naturalness": 80.0,
            "identity_consistency": 80.0,
            "temporal_stability": 80.0,
            "camera_motion": 80.0,
            "composition": 80.0,
            "visual_quality": 80.0,
            "prompt_alignment": 80.0,
            "platform_fit": 80.0,
        }
        if asset is None or not asset.path:
            return _result(score=0, reasons=["fail: missing video asset"], judge_type=self.name, breakdown={key: 0.0 for key in breakdown})
        if asset.type not in {"video", "final"}:
            reasons.append("fail: not a video")
        duration = asset.duration or 0
        wanted = float(context.get("duration_seconds") or 0)
        if wanted and duration and abs(duration - wanted) > max(4.0, wanted * 0.5):
            breakdown["platform_fit"] = 55.0
            reasons.append("duration far from brief")
        aspect = str(context.get("aspect_ratio") or "9:16")
        if aspect == "9:16":
            breakdown["platform_fit"] = max(breakdown["platform_fit"], 82.0)
        score = sum(breakdown.values()) / len(breakdown)
        if any(item.startswith("fail:") for item in reasons):
            score = min(score, 40.0)
        return _result(score=score, reasons=reasons, judge_type=self.name, breakdown=breakdown, asset_id=asset.asset_id)


class ConsistencyJudge:
    name = "consistency"

    def judge(self, assets: list[MediaAsset], *, context: dict[str, Any] | None = None) -> JudgeResult:
        reasons: list[str] = []
        breakdown = {
            "face": 80.0,
            "hair": 80.0,
            "wardrobe": 80.0,
            "environment": 80.0,
            "lighting": 80.0,
            "camera": 80.0,
            "character_position": 80.0,
            "story_continuity": 80.0,
        }
        ids = {asset.character_id for asset in assets if asset.character_id}
        if len(ids) > 1:
            breakdown["face"] = 30.0
            reasons.append("fail: multiple character identities")
        if not assets:
            return _result(score=0, reasons=["fail: no shots"], judge_type=self.name, breakdown={key: 0.0 for key in breakdown})
        score = sum(breakdown.values()) / len(breakdown)
        if any(item.startswith("fail:") for item in reasons):
            score = min(score, 40.0)
        return _result(score=score, reasons=reasons, judge_type=self.name, breakdown=breakdown, asset_id=assets[0].asset_id)


class PlatformFitJudge:
    name = "platform_fit"

    def judge(self, asset: MediaAsset | None, *, context: dict[str, Any] | None = None) -> JudgeResult:
        context = context or {}
        breakdown = {"aspect_ratio": 80.0, "duration": 80.0, "safe_area": 80.0}
        reasons: list[str] = []
        if asset is None:
            return _result(score=0, reasons=["fail: missing asset"], judge_type=self.name, breakdown=breakdown)
        wanted = str(context.get("aspect_ratio") or "9:16")
        if wanted == "9:16" and asset.width and asset.height and asset.width > asset.height:
            breakdown["aspect_ratio"] = 40.0
            reasons.append("fail: landscape asset for 9:16")
        score = sum(breakdown.values()) / len(breakdown)
        if any(item.startswith("fail:") for item in reasons):
            score = min(score, 40.0)
        return _result(score=score, reasons=reasons, judge_type=self.name, breakdown=breakdown, asset_id=asset.asset_id)


class ContentFitJudge:
    name = "content_fit"

    def judge(self, asset: MediaAsset | None, *, context: dict[str, Any] | None = None) -> JudgeResult:
        context = context or {}
        breakdown = {"brief_alignment": 82.0, "commerce_restraint": 85.0}
        reasons: list[str] = []
        if context.get("commerce_intent") not in {None, "", "none"} and context.get("content_first", True) is False:
            breakdown["commerce_restraint"] = 50.0
            reasons.append("commerce intent without content-first brief")
        if asset is None:
            return _result(score=0, reasons=["fail: missing asset"], judge_type=self.name, breakdown=breakdown)
        score = sum(breakdown.values()) / len(breakdown)
        return _result(score=score, reasons=reasons, judge_type=self.name, breakdown=breakdown, asset_id=asset.asset_id)


class TechnicalQA:
    name = "technical"

    def inspect_image(self, asset: MediaAsset) -> dict[str, str]:
        failures = []
        if not asset.mime_type.startswith("image/") and asset.type == "image":
            failures.append("format")
        if asset.size <= 0:
            failures.append("size")
        if not asset.width or not asset.height:
            failures.append("resolution")
        return {"decision": "pass" if not failures else "fail", "failures": failures}

    def inspect_video(self, asset: MediaAsset) -> dict[str, str]:
        failures = []
        if asset.mime_type and not asset.mime_type.startswith("video/") and asset.type == "video":
            failures.append("codec")
        if asset.size <= 0:
            failures.append("file_size")
        if not asset.width or not asset.height:
            failures.append("resolution")
        return {"decision": "pass" if not failures else "fail", "failures": failures}


class RegenerationStrategy:
    def next_action(self, attempt: int, *, last: JudgeResult | None = None) -> str:
        if attempt >= len(REGENERATION_STRATEGIES):
            return "stop"
        return REGENERATION_STRATEGIES[attempt]


def rank_assets(pairs: list[tuple[MediaAsset, JudgeResult]]) -> list[tuple[MediaAsset, JudgeResult]]:
    return sorted(pairs, key=lambda item: item[1].score, reverse=True)


JUDGES = {
    "image": ImageJudge(),
    "video": VideoJudge(),
    "consistency": ConsistencyJudge(),
    "platform_fit": PlatformFitJudge(),
    "content_fit": ContentFitJudge(),
    "continuity": ConsistencyJudge(),
}
