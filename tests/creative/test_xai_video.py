from creative.errors import ProviderBlocked, UnsupportedCapability
from creative.providers.resolver import GenerationProviderResolver
from creative.providers.xai.adapter import XAIVideoAdapter
from creative.providers.xai.client import VIDEO_CONTRACT_VERIFIED, VIDEO_MODEL, VIDEO_NOT_VERIFIED


def test_xai_video_model_is_imagine_not_grok_coding_agent():
    adapter = XAIVideoAdapter()
    assert adapter.client.model == "grok-imagine-video-1.5"
    assert VIDEO_MODEL == "grok-imagine-video-1.5"
    assert VIDEO_CONTRACT_VERIFIED is False
    status = adapter.capability_status("text_to_video")
    assert status["status"] == "NOT_VERIFIED"
    assert status["VIDEO_CONTRACT_VERIFIED"] is False
    assert status["model"] == "grok-imagine-video-1.5"
    assert "Grok 4.6" not in VIDEO_NOT_VERIFIED


def test_xai_does_not_generate_images():
    adapter = XAIVideoAdapter()
    try:
        adapter.generate_image({"prompt": "x"})
        assert False, "xAI must not own image generation"
    except UnsupportedCapability:
        pass


def test_resolver_routes_video_to_xai_and_blocks_unverified_contract():
    resolver = GenerationProviderResolver(allow_mock=False)
    assert "xai" in resolver.providers
    assert "mock" not in resolver.providers
    adapter = resolver.providers["xai"]
    try:
        adapter.create_task("generate_video", {"prompt": "continue the series"})
        assert False, "unverified xAI contract must fail closed"
    except ProviderBlocked:
        pass
