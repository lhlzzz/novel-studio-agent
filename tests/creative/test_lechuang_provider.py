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
