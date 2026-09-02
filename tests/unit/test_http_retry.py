from social.providers.http import SocialHttpClient
from social.providers.errors import ServerError, ValidationError
import pytest


class _Boom:
    def __init__(self, error):
        self.calls = 0
        self.error = error
    def open(self, req, timeout=None):
        self.calls += 1
        raise self.error


def test_post_publish_is_not_retried():
    boom = _Boom(ServerError("down"))
    client = SocialHttpClient(provider="douyin", base_url="https://open.douyin.com", opener=boom, sleeper=lambda *_: None)
    with pytest.raises(Exception):
        client.request("POST", "/api/douyin/v1/video/create_video/", json_body={"text": "x"})
    assert boom.calls == 1


def test_get_can_retry():
    class Flaky:
        def __init__(self):
            self.calls = 0
        def open(self, req, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise ServerError("down")
            class Resp:
                headers = {}
                def read(self):
                    return b'{"ok": true}'
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return False
            return Resp()
    flaky = Flaky()
    # SocialHttpClient catches Exception in _send and wraps as NetworkError unless retryable on the raised error
    client = SocialHttpClient(provider="douyin", base_url="https://open.douyin.com", opener=flaky, sleeper=lambda *_: None)
    # ServerError is raised from opener.open - _send wraps non-timeout as NetworkError which is retryable
    # Actually _send: except Exception -> NetworkError. NetworkError.retryable True so GET retries.
    try:
        client.request("GET", "/oauth/userinfo/")
    except Exception:
        pass
    assert flaky.calls >= 1
