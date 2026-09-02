from __future__ import annotations

from typing import Any

from social.providers.errors import CapabilityUnsupported
from social.providers.http import SocialHttpClient


class XiaohongshuClient:
    def __init__(self, *, http: SocialHttpClient | None = None) -> None:
        self.http = http or SocialHttpClient(provider="xiaohongshu", base_url="")

    def publish_direct(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise CapabilityUnsupported("Xiaohongshu direct_publish is BLOCKED: no verified official server-side publish API")
