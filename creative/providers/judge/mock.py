"""Test-only vision judge. Inspects real files; never reported as live."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from creative.schemas import Character, JudgeResult, MediaAsset, utcnow

PASS_SCORE = 70.0


class MockVisionJudgeProvider:
    name = "mock-vision"

    def live_ready(self) -> tuple[bool, str]:
        return True, "mock"

    def judge_image(self, asset: MediaAsset, *, brief: dict[str, Any] | None = None, character: Character | None = None, reference: MediaAsset | None = None) -> JudgeResult:
        return self._score(asset, judge_type="image", brief=brief or {}, character=character, reference=reference)

    def judge_video(self, asset: MediaAsset, *, brief: dict[str, Any] | None = None, character: Character | None = None, reference: MediaAsset | None = None) -> JudgeResult:
        return self._score(asset, judge_type="video", brief=brief or {}, character=character, reference=reference)

    def judge_frames(self, frames: list[str], *, brief: dict[str, Any] | None = None, character: Character | None = None, reference: MediaAsset | None = None) -> JudgeResult:
        existing = [item for item in frames if Path(item).is_file()]
        score = 82.0 if existing else 0.0
        reasons = [] if existing else ["fail: no frames"]
        breakdown = {"identity": score, "temporal_consistency": score, "motion": score, "composition": score, "prompt_alignment": score, "artifact": score}
        return self._result(score, reasons, "video", breakdown)

    def judge_consistency(self, assets: list[MediaAsset], *, brief: dict[str, Any] | None = None, character: Character | None = None, reference: MediaAsset | None = None) -> JudgeResult:
        breakdown = {key: 84.0 for key in ("face", "hair", "wardrobe", "age", "body", "lighting", "scene", "props", "camera")}
        reasons: list[str] = []
        if not assets:
            return self._result(0, ["fail: no shots"], "consistency", {key: 0.0 for key in breakdown})
        ids = {item.character_id for item in assets if item.character_id}
        if len(ids) > 1:
            breakdown["face"] = 30.0
            reasons.append("fail: multiple character identities")
        if character and any(item.character_id and item.character_id != character.character_id for item in assets):
            breakdown["face"] = 30.0
            reasons.append("fail: identity mismatch")
        score = sum(breakdown.values()) / len(breakdown)
        if any(item.startswith("fail:") for item in reasons):
            score = min(score, 40.0)
        return self._result(score, reasons, "consistency", breakdown, asset_id=assets[0].asset_id)

    def _score(self, asset: MediaAsset, *, judge_type: str, brief: dict[str, Any], character: Character | None, reference: MediaAsset | None) -> JudgeResult:
        if asset is None or not asset.path:
            keys = ("composition", "identity", "artifact")
            return self._result(0, ["fail: missing asset"], judge_type, {key: 0.0 for key in keys})
        path = Path(asset.path)
        reasons: list[str] = []
        breakdown = {
            "composition": 78.0,
            "face_quality": 80.0,
            "identity_consistency": 80.0,
            "artifact_score": 80.0,
            "lighting": 80.0,
            "aesthetic": 80.0,
            "content_fit": 82.0,
            "prompt_alignment": 80.0,
        }
        if not path.is_file() or path.stat().st_size <= 0:
            return self._result(0, ["fail: missing file"], judge_type, {key: 0.0 for key in breakdown}, asset_id=asset.asset_id)
        if judge_type == "image":
            try:
                from PIL import Image
                with Image.open(path) as image:
                    width, height = image.size
                breakdown["composition"] = 86.0 if width >= 64 and height >= 64 else 40.0
                wanted = str(brief.get("aspect_ratio") or "")
                if wanted == "9:16" and width / max(height, 1) > 0.7:
                    breakdown["composition"] = 60.0
                    reasons.append("aspect ratio drifts from 9:16")
            except Exception:
                reasons.append("fail: unreadable image")
                breakdown["artifact_score"] = 20.0
        else:
            try:
                from creative.render.ffmpeg import video_info
                info = video_info(path)
                if not info.get("width") or not info.get("duration"):
                    reasons.append("fail: invalid video")
                    breakdown["artifact_score"] = 20.0
                else:
                    breakdown["composition"] = 84.0
            except Exception:
                reasons.append("fail: unreadable video")
                breakdown["artifact_score"] = 20.0
        if character and asset.character_id and asset.character_id != character.character_id:
            breakdown["identity_consistency"] = 40.0
            reasons.append("fail: identity mismatch")
        if brief.get("character_id") and asset.character_id and asset.character_id != brief.get("character_id"):
            breakdown["identity_consistency"] = 40.0
            reasons.append("fail: identity mismatch")
        if reference and not Path(reference.path).is_file():
            reasons.append("reference missing")
        score = sum(breakdown.values()) / len(breakdown)
        if any(item.startswith("fail:") for item in reasons):
            score = min(score, 40.0)
        return self._result(score, reasons, judge_type, breakdown, asset_id=asset.asset_id)

    def _result(self, score: float, reasons: list[str], judge_type: str, breakdown: dict[str, float], asset_id: str | None = None) -> JudgeResult:
        decision = "PASS" if score >= PASS_SCORE and not any(item.startswith("fail:") for item in reasons) else "FAIL"
        return JudgeResult(
            score=round(score, 2),
            decision=decision,
            reasons=tuple(reasons),
            judge_type=judge_type,
            judge_model="mock-vision",
            judge_version="mock-v1",
            breakdown=breakdown,
            timestamp=utcnow(),
            asset_id=asset_id,
            judge_id=uuid4().hex,
            judge_provider=self.name,
            passed=decision == "PASS",
            violations=tuple(item for item in reasons if item.startswith("fail:")),
            warnings=tuple(item for item in reasons if not item.startswith("fail:")),
        )
