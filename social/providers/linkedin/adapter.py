"""Native linkedin adapter. REGISTERED/BLOCKED until credentials are verified."""

from __future__ import annotations

from typing import Any

from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.providers.base import BaseSocialAdapter
from social.providers.errors import AuthenticationError
from social.providers.linkedin.capabilities import CLAIMED
from social.providers.linkedin.client import LinkedInClient

class LinkedInAdapter(BaseSocialAdapter):
    provider = "linkedin"
    platform = "linkedin"
    api_base = "https://api.linkedin.com/rest"
    claimed = CLAIMED

    def __init__(self, *, client: LinkedInClient | None = None, secrets: Any | None = None) -> None:
        http = None if client is None else client.http
        super().__init__(client=http, secrets=secrets)
        self.api = client or LinkedInClient(http=self.client)

    def _discover_accounts(self, creds: dict[str, Any]) -> list[SocialAccount]:
        raise AuthenticationError("linkedin account discovery is BLOCKED until OAuth completes")

    def _validate_platform(self, job, account) -> list[str]:
        errors: list[str] = []
        if not job.variant.body.strip() and not job.variant.media:
            errors.append("LinkedIn requires text or media")
        return errors
