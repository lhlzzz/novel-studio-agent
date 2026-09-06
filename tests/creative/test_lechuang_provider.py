import pytest

from creative.errors import ProviderBlocked, UnsupportedCapability
from creative.providers.lechuang.adapter import LechuangAdapter
from creative.providers.lechuang.client import DEFAULT_VIDEO_MODEL, VIDEO_CONTRACT_VERIFIED, VIDEO_NOT_VERIFIED, LechuangClient
from creative.providers.resolver import GenerationProviderResolver


def test_lechuang_live_is_blocked_without_contract(monkeypatch):
    monkeypatch.delenv("XIAOLEAI_API_KEY", raising=False)
    monkeypatch.delenv("XIAOLEAI_BASE_URL", raising=False)
    adapter = LechuangAdapter(client=LechuangClient(base_url="", api_key=""))
    ready, reason = adapter.live_ready()
    assert ready is False
    assert "XIAOLEAI_API_KEY" in reason
    with pytest.raises(ProviderBlocked):
        adapter.generate_image({"prompt": "nope"})


def test_lechuang_does_not_guess_video(monkeypatch):
    adapter = LechuangAdapter(client=LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret"))
    ready, reason = adapter.live_ready()
    assert ready is True
    with pytest.raises(UnsupportedCapability):
        adapter.extend_video({"prompt": "nope"})


def test_lechuang_typed_contracts_exist_but_stay_unverified():
    from creative.providers.lechuang.schemas import (
        CreateImageRequest,
        CreateImageToImageRequest,
        CreateImageToVideoRequest,
        CreateTaskResponse,
        CreateVideoRequest,
        ProviderError,
        TaskResultResponse,
        TaskStatusResponse,
    )
    image = CreateImageRequest(prompt="one person one scene")
    video = CreateImageToVideoRequest(prompt="lock identity", source_asset_id="asset")
    assert image.prompt and video.source_asset_id
    assert CreateVideoRequest(prompt="x").prompt == "x"
    assert CreateImageToImageRequest(prompt="x").prompt == "x"
    assert CreateTaskResponse(task_id="t", status="queued").status == "queued"
    assert TaskStatusResponse(task_id="t", status="processing").status == "processing"
    assert TaskResultResponse(task_id="t", status="completed").asset_id is None
    assert ProviderError(code="invalid_response", message="nope").retryable is False
    adapter = LechuangAdapter(client=LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret"))
    assert adapter.live_ready()[0] is True
    with pytest.raises(UnsupportedCapability):
        adapter.edit_video({"prompt": "nope"})


def test_lechuang_is_the_only_creative_provider():
    resolver = GenerationProviderResolver(allow_mock=False)
    assert set(resolver.providers) == {"lechuang"}
    assert "xai" not in resolver.providers
    assert "mock" not in resolver.providers


def test_lechuang_owns_image_and_video():
    adapter = LechuangAdapter(client=LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret"))
    assert adapter.name == "lechuang"
    assert DEFAULT_VIDEO_MODEL == "grok-video"
    assert VIDEO_CONTRACT_VERIFIED is False
    image = adapter.capability_status("text_to_image")
    video = adapter.capability_status("text_to_video")
    i2v = adapter.capability_status("image_to_video")
    assert image["verified"] is True
    assert video["verified"] is False
    assert i2v["verified"] is False
    assert video["status"] in {"NOT_VERIFIED", "CONFIGURED"}
    assert "Grok 4.6" not in VIDEO_NOT_VERIFIED
    assert "grok-4.6" not in VIDEO_NOT_VERIFIED


def test_resolver_aliases_removed_xai_name_to_lechuang():
    adapter = LechuangAdapter(client=LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret"))
    resolver = GenerationProviderResolver(providers={"lechuang": adapter}, allow_mock=False)
    resolved, name = resolver.resolve("xai")
    assert name == "lechuang"
    assert resolved is adapter


def test_unverified_lechuang_video_stays_fail_closed():
    adapter = LechuangAdapter(client=LechuangClient(base_url="", api_key=""))
    with pytest.raises(ProviderBlocked):
        adapter.create_task("generate_video", {"prompt": "continue the series"})
