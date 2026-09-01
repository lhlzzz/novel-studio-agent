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
    assert result.passed is (result.decision == "PASS")
    assert isinstance(result.violations, tuple)
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


def test_gateway_vision_blocks_without_credentials(monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    monkeypatch.delenv("VISION_API_KEY", raising=False)
    monkeypatch.delenv("XIAOMI_API_KEY", raising=False)
    monkeypatch.delenv("AI_GATEWAY_API_URL", raising=False)
    monkeypatch.delenv("VISION_API_URL", raising=False)
    monkeypatch.delenv("XIAOMI_BASE_URL", raising=False)
    from creative.providers.judge.gateway import GatewayVisionProvider
    provider = GatewayVisionProvider()
    ready, reason = provider.live_ready()
    assert ready is False
    assert "AI_GATEWAY_API_KEY" in reason
