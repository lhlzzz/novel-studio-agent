"""Native youtube adapter. REGISTERED/BLOCKED until credentials are verified."""

from __future__ import annotations

from typing import Any

from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.providers.base import BaseSocialAdapter
from social.providers.errors import AuthenticationError
from social.providers.youtube.capabilities import CLAIMED
from social.providers.youtube.client import YouTubeClient

class YouTubeAdapter(BaseSocialAdapter):
    provider = "youtube"
    platform = "youtube"
    api_base = "https://www.googleapis.com/youtube/v3"
    claimed = CLAIMED

    def __init__(self, *, client: YouTubeClient | None = None, secrets: Any | None = None) -> None:
        http = None if client is None else client.http
        super().__init__(client=http, secrets=secrets)
        self.api = client or YouTubeClient(http=self.client)

    def _discover_accounts(self, creds: dict[str, Any]) -> list[SocialAccount]:
        raise AuthenticationError("youtube account discovery is BLOCKED until OAuth completes")

    def _validate_platform(self, job, account) -> list[str]:
        errors: list[str] = []
        if not job.variant.media:
            errors.append("YouTube requires a video")
        if not (job.variant.title or job.variant.body):
            errors.append("YouTube requires a title")
        return errors
