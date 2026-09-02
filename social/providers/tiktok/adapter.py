"""Native tiktok adapter. REGISTERED/BLOCKED until credentials are verified."""

from __future__ import annotations

from typing import Any

from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.providers.base import BaseSocialAdapter
from social.providers.errors import AuthenticationError
from social.providers.tiktok.capabilities import CLAIMED
from social.providers.tiktok.client import TikTokClient

class TikTokAdapter(BaseSocialAdapter):
    provider = "tiktok"
    platform = "tiktok"
    api_base = "https://open.tiktokapis.com/v2"
    claimed = CLAIMED

    def __init__(self, *, client: TikTokClient | None = None, secrets: Any | None = None) -> None:
        http = None if client is None else client.http
        super().__init__(client=http, secrets=secrets)
        self.api = client or TikTokClient(http=self.client)

    def _discover_accounts(self, creds: dict[str, Any]) -> list[SocialAccount]:
        raise AuthenticationError("tiktok account discovery is BLOCKED until OAuth completes")

    def _validate_platform(self, job, account) -> list[str]:
        errors: list[str] = []
        if not job.variant.media:
            errors.append("TikTok requires a video")
        return errors
