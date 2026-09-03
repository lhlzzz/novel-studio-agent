import pytest

from creative.errors import AuthError, ProviderBlocked, RateLimited, UnsupportedCapability
from creative.providers.base import CANONICAL_CAPABILITIES, CreativeProvider
from creative.providers.lechuang.adapter import LechuangAdapter
from creative.providers.lechuang.client import LechuangClient
from creative.providers.mock import MockGenerationProvider


def test_mock_provider_contract(tmp_path):
    provider = MockGenerationProvider()
    matrix = provider.capabilities()
    assert set(CANONICAL_CAPABILITIES).issubset(matrix)
    assert matrix["image_generation"] is True
    task = provider.create("generate_image", {"prompt": "x", "width": 64, "height": 64})
    polled = provider.poll(task.provider_task_id)
    assert polled.status in {"succeeded", "queued", "running"}
    result = provider.result(task.provider_task_id)
    assert result
    cancelled = provider.cancel(task.provider_task_id)
    assert cancelled.status in {"cancelled", "succeeded"}
    health = provider.health()
    assert health["ok"] is True


def test_lechuang_auth_and_rate_limit(monkeypatch):
    adapter = LechuangAdapter(client=LechuangClient(base_url="", api_key=""))
    assert adapter.health()["ok"] is False
    with pytest.raises((ProviderBlocked, AuthError)):
        adapter.create("generate_image", {"prompt": "x"})
    client = LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret")
    with pytest.raises(RateLimited):
        client.handle_rate_limit(429, {"Retry-After": "2"})
    ready, reason = adapter.live_ready()
    assert ready is False
    assert "XIAOLEAI_API_KEY" in reason


def test_lechuang_timeout_and_error_do_not_guess():
    adapter = LechuangAdapter(client=LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret"))
    with pytest.raises((ProviderBlocked, UnsupportedCapability)):
        adapter.poll("missing")
    with pytest.raises((ProviderBlocked, UnsupportedCapability)):
        adapter.result("missing")


def test_lechuang_http_errors_are_mapped():
    client = LechuangClient(base_url="https://example.invalid", api_key="secret")
    with pytest.raises(AuthError):
        client.map_http_error(401, "{}")
    with pytest.raises(RateLimited):
        client.map_http_error(429, "{}", {"Retry-After": "1"})
    with pytest.raises(ProviderBlocked):
        client.map_http_error(500, "oops")
    with pytest.raises(ProviderBlocked):
        client.map_http_error(400, "bad")
