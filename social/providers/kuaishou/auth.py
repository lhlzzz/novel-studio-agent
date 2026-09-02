from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

from social.auth.credentials import CredentialRecord
from social.auth.oauth import OAuthStart, RevokeResult, generate_state
from social.providers.errors import AuthenticationError
from social.providers.http import SocialHttpClient
from social.providers.kuaishou.contract import AUTHORIZE_URL, REFRESH_URL, TOKEN_URL


DEFAULT_SCOPES = "user_info,user_video_publish"


class KuaishouAuth:
    def __init__(self, *, client: SocialHttpClient | None = None) -> None:
        self.app_id = os.getenv("KUAISHOU_APP_ID", "").strip() or os.getenv("KUAISHOU_CLIENT_ID", "").strip()
        self.app_secret = os.getenv("KUAISHOU_APP_SECRET", "").strip() or os.getenv("KUAISHOU_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.getenv("KUAISHOU_REDIRECT_URI", "").strip()
        self.client = client or SocialHttpClient(provider="kuaishou", base_url="https://open.kuaishou.com")

    def available(self) -> bool:
        return bool(self.app_id and self.app_secret and self.redirect_uri)

    def scopes(self) -> str:
        return os.getenv("KUAISHOU_SCOPES", DEFAULT_SCOPES)

    def authorization_url(self, *, state: str | None = None, redirect_uri: str | None = None) -> OAuthStart:
        if not self.available():
            raise AuthenticationError("Kuaishou OAuth is BLOCKED: KUAISHOU_APP_ID/SECRET and KUAISHOU_REDIRECT_URI are required")
        params = {
            "app_id": self.app_id,
            "scope": self.scopes(),
            "response_type": "code",
            "redirect_uri": redirect_uri or self.redirect_uri,
            "state": state or generate_state(),
        }
        return OAuthStart(url=f"{AUTHORIZE_URL}?{urlencode(params)}", state=params["state"], provider="kuaishou", redirect_uri=params["redirect_uri"], scopes=self.scopes())

    def exchange_code(self, code: str, *, code_verifier: str = "", redirect_uri: str | None = None) -> CredentialRecord:
        payload = self.client.request(
            "POST",
            TOKEN_URL,
            query={
                "app_id": self.app_id,
                "app_secret": self.app_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
            absolute=True,
        )
        data = payload if isinstance(payload, dict) else {}
        if not data.get("access_token"):
            raise AuthenticationError(f"Kuaishou token exchange did not return access_token: {payload}")
        return CredentialRecord.from_payload({**data, "provider": "kuaishou", "scope": data.get("scope") or self.scopes()})

    def refresh(self, refresh_token: str) -> CredentialRecord:
        payload = self.client.request(
            "POST",
            REFRESH_URL,
            query={
                "app_id": self.app_id,
                "app_secret": self.app_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            absolute=True,
        )
        data = payload if isinstance(payload, dict) else {}
        if not data.get("access_token"):
            raise AuthenticationError(f"Kuaishou refresh did not return access_token: {payload}")
        return CredentialRecord.from_payload({**data, "provider": "kuaishou"})

    def revoke(self, token: str, *, token_type_hint: str = "access_token") -> RevokeResult:
        return RevokeResult(remote_revoked=False, unsupported=True, reason="Kuaishou has no public revoke endpoint")

    def validate(self, access_token: str) -> dict[str, Any]:
        return self.client.request("GET", "/openapi/user_info", query={"app_id": self.app_id, "access_token": access_token})
