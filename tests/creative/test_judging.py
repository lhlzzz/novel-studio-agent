from creative.assets import MIN_PNG, persist_bytes
from creative.errors import JudgeBlocked
from creative.judges import ImageJudge, VideoJudge
from creative.providers.judge.mock import MockVisionJudgeProvider


def test_judges_return_score_decision_reason(tmp_path):
    image = persist_bytes(MIN_PNG, asset_type="image", suffix=".png", root=tmp_path, mime_type="image/png", width=720, height=1280)
    provider = MockVisionJudgeProvider()
    result = ImageJudge(provider).judge(image, context={"aspect_ratio": "9:16", "face_visible": False})
    assert result.decision in {"PASS", "FAIL"}
    assert result.score >= 0
    assert result.judge_version
    assert result.judge_provider == "mock-vision"
    missing = VideoJudge(provider).judge(None)
    assert missing.decision == "FAIL"
    assert missing.reasons


def test_judge_without_provider_is_blocked(tmp_path):
    image = persist_bytes(MIN_PNG, asset_type="image", suffix=".png", root=tmp_path, mime_type="image/png", width=720, height=1280)
    try:
        ImageJudge().judge(image)
    except JudgeBlocked:
        return
    raise AssertionError("expected JudgeBlocked")
