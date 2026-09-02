"""Official linkedin OAuth. Missing credentials stay BLOCKED."""

from __future__ import annotations

import os

from social.providers.errors import AuthenticationError

class LinkedInAuth:
    def __init__(self) -> None:
        self.client_id = os.getenv("LINKEDIN_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI", "").strip()

    def available(self) -> bool:
        return bool(self.client_id and self.redirect_uri)

    def authorization_url(self) -> dict[str, str]:
        if not self.available():
            raise AuthenticationError("linkedin OAuth is BLOCKED until client credentials exist")
        return {"url": "", "state": ""}
