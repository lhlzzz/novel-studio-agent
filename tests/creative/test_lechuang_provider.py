import pytest

from creative.errors import ProviderBlocked, UnsupportedCapability
from creative.providers.lechuang.adapter import LechuangAdapter
from creative.providers.lechuang.client import LechuangClient


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
    assert TaskResultResponse(task_id="t", status="completed").asset_id is None
    assert ProviderError(code="invalid_response", message="nope").retryable is False
    adapter = LechuangAdapter(client=LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret"))
    assert adapter.live_ready()[0] is True
    with pytest.raises(UnsupportedCapability):
        adapter.generate_video({"prompt": "nope"})
