from creative.assets import MIN_PNG, persist_bytes
from creative.judge import ImageJudge, VideoJudge


def test_judges_return_score_decision_reason(tmp_path):
    image = persist_bytes(MIN_PNG, asset_type="image", suffix=".png", root=tmp_path, mime_type="image/png", width=720, height=1280)
    result = ImageJudge().judge(image, context={"aspect_ratio": "9:16", "face_visible": False})
    assert result.decision in {"PASS", "FAIL"}
    assert result.score >= 0
    assert result.judge_version
    missing = VideoJudge().judge(None)
    assert missing.decision == "FAIL"
    assert missing.reasons
