"""Native instagram adapter. REGISTERED/BLOCKED until credentials are verified."""

from __future__ import annotations

from typing import Any

from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.providers.base import BaseSocialAdapter
from social.providers.errors import AuthenticationError
from social.providers.instagram.capabilities import CLAIMED
from social.providers.instagram.client import InstagramClient

class InstagramAdapter(BaseSocialAdapter):
    provider = "instagram"
    platform = "instagram"
    api_base = "https://graph.facebook.com/v21.0"
    claimed = CLAIMED

    def __init__(self, *, client: InstagramClient | None = None, secrets: Any | None = None) -> None:
        http = None if client is None else client.http
        super().__init__(client=http, secrets=secrets)
        self.api = client or InstagramClient(http=self.client)

    def _discover_accounts(self, creds: dict[str, Any]) -> list[SocialAccount]:
        raise AuthenticationError("instagram account discovery is BLOCKED until OAuth completes")

    def _validate_platform(self, job, account) -> list[str]:
        errors: list[str] = []
        if not job.variant.media:
            errors.append("Instagram requires media")
        return errors
