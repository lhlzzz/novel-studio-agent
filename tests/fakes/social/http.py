from typing import Any, Callable


class FakeHttp:
    def __init__(self, handler: Callable[[str, str, dict], Any]):
        self.handler = handler
        self.calls = []
        self.rate_limit = {"remaining": None, "reset_at": None, "retry_after": None}

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return self.handler(method, path, kwargs)
