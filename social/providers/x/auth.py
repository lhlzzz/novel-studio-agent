"""X OAuth 2.0 Authorization Code with PKCE. Official token endpoint only."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from typing import Any
from urllib.parse import urlencode

from social.providers.errors import AuthenticationError
from social.providers.http import SocialHttpClient

AUTHORIZE_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
REVOKE_URL = "https://api.x.com/2/oauth2/revoke"
DEFAULT_SCOPES = "tweet.read tweet.write users.read offline.access media.write"


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


class XAuth:
    def __init__(self, *, client: SocialHttpClient | None = None) -> None:
        self.client_id = os.getenv("X_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("X_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.getenv("X_REDIRECT_URI", "").strip()
        self.client = client or SocialHttpClient(provider="x", base_url="https://api.x.com/2")

    def available(self) -> bool:
        return bool(self.client_id and self.redirect_uri)

    def authorization_url(self, *, state: str | None = None) -> dict[str, str]:
        if not self.available():
            raise AuthenticationError("X OAuth is BLOCKED: X_CLIENT_ID and X_REDIRECT_URI are required")
        verifier, challenge = _pkce()
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": DEFAULT_SCOPES,
            "state": state or secrets.token_urlsafe(16),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return {"url": f"{AUTHORIZE_URL}?{urlencode(params)}", "code_verifier": verifier, "state": params["state"]}

    def exchange_code(self, code: str, *, code_verifier: str) -> dict[str, Any]:
        if not self.available():
            raise AuthenticationError("X OAuth is BLOCKED: X_CLIENT_ID and X_REDIRECT_URI are required")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        body = urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": code_verifier,
        }).encode("utf-8")
        if self.client_secret:
            basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode("ascii")).decode("ascii")
            headers["Authorization"] = f"Basic {basic}"
        return self.client.request("POST", TOKEN_URL, headers=headers, data=body, absolute=True)

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        if not refresh_token:
            raise AuthenticationError("X refresh_token missing")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        body = urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }).encode("utf-8")
        return self.client.request("POST", TOKEN_URL, headers=headers, data=body, absolute=True)

    def revoke(self, token: str) -> None:
        if not token:
            return
        body = urlencode({"token": token, "client_id": self.client_id, "token_type_hint": "access_token"}).encode("utf-8")
        self.client.request("POST", REVOKE_URL, headers={"Content-Type": "application/x-www-form-urlencoded"}, data=body, absolute=True)
