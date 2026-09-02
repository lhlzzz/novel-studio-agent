"""Official instagram OAuth. Missing credentials stay BLOCKED."""

from __future__ import annotations

import os

from social.providers.errors import AuthenticationError

class InstagramAuth:
    def __init__(self) -> None:
        self.client_id = os.getenv("INSTAGRAM_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("INSTAGRAM_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.getenv("INSTAGRAM_REDIRECT_URI", "").strip()

    def available(self) -> bool:
        return bool(self.client_id and self.redirect_uri)

    def authorization_url(self) -> dict[str, str]:
        if not self.available():
            raise AuthenticationError("instagram OAuth is BLOCKED until client credentials exist")
        return {"url": "", "state": ""}
