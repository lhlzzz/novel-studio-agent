import pytest

from creative.errors import ProviderBlocked, UnsupportedCapability
from creative.providers.lechuang.adapter import LechuangAdapter
from creative.providers.lechuang.client import LechuangClient


def test_lechuang_live_is_blocked_without_contract(monkeypatch):
    monkeypatch.delenv("LECHUANG_API_KEY", raising=False)
    monkeypatch.delenv("LECHUANG_API_URL", raising=False)
    adapter = LechuangAdapter(client=LechuangClient(base_url="", api_key=""))
    ready, reason = adapter.live_ready()
    assert ready is False
    assert "LECHUANG_API_KEY" in reason
    with pytest.raises(ProviderBlocked):
        adapter.generate_image({"prompt": "nope"})


def test_lechuang_does_not_guess_with_key_only(monkeypatch):
    adapter = LechuangAdapter(client=LechuangClient(base_url="https://example.invalid", api_key="secret"))
    ready, reason = adapter.live_ready()
    assert ready is False
    assert ready is False and ("blocked" in reason.lower() or "contract" in reason.lower() or "extractable" in reason.lower())
    with pytest.raises((ProviderBlocked, UnsupportedCapability)):
        adapter.generate_video({"prompt": "nope"})


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
    assert TaskResultResponse(task_id="t", status="completed").media_url is None
    assert ProviderError(code="invalid_response", message="nope").retryable is False
    adapter = LechuangAdapter(client=LechuangClient(base_url="https://example.invalid", api_key="secret"))
    assert adapter.live_ready()[0] is False
