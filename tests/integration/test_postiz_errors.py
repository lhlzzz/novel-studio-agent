from integrations.providers.postiz.client import PostizClient
from integrations.providers.postiz.errors import RateLimitError, ServerError, classify_http_error


class FakeHTTPError(Exception):
    def __init__(self, code, headers=None, body=b""):
        self.code = code
        self.headers = headers or {}
        self._body = body
        self.reason = "error"

    def read(self):
        return self._body


def test_failed_provider_is_retryable():
    err = classify_http_error(503, "bad gateway")
    assert isinstance(err, ServerError)
    assert err.retryable is True
    limited = classify_http_error(429, "slow down", retry_after=2)
    assert isinstance(limited, RateLimitError)
    assert limited.retry_after == 2


def test_retry_stops_after_max_attempts():
    sleeps = []
    calls = {"n": 0}

    def opener(request, timeout=0):
        from urllib.error import URLError
        calls["n"] += 1
        raise URLError("down")

    client = PostizClient(base_url="http://postiz.test", api_key="k", max_attempts=3, sleeper=lambda s: sleeps.append(s), opener=opener)
    try:
        client.list_integrations()
    except Exception as exc:
        assert "network" in str(exc).lower() or "down" in str(exc).lower()
    else:
        raise AssertionError("expected network failure")
    assert calls["n"] == 3
    assert sleeps == [0.5, 1.0]
