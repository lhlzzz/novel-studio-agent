from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

from social.auth.credentials import CredentialRecord
from social.auth.oauth import OAuthStart, RevokeResult, generate_state
from social.providers.douyin.client import unwrap_douyin
from social.providers.douyin.contract import AUTHORIZE_URL, REFRESH_URL, TOKEN_URL, USERINFO_URL
from social.providers.errors import AuthenticationError
from social.providers.http import SocialHttpClient


DEFAULT_SCOPES = "user_info,video.create,video.data,video.list"


class DouyinAuth:
    def __init__(self, *, client: SocialHttpClient | None = None) -> None:
        self.client_key = os.getenv("DOUYIN_CLIENT_KEY", "").strip() or os.getenv("DOUYIN_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("DOUYIN_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.getenv("DOUYIN_REDIRECT_URI", "").strip()
        self.client = client or SocialHttpClient(provider="douyin", base_url="https://open.douyin.com")

    def available(self) -> bool:
        return bool(self.client_key and self.client_secret and self.redirect_uri)

    def scopes(self) -> str:
        return os.getenv("DOUYIN_SCOPES", DEFAULT_SCOPES)

    def authorization_url(self, *, state: str | None = None, redirect_uri: str | None = None) -> OAuthStart:
        if not self.available():
            raise AuthenticationError("Douyin OAuth is BLOCKED: DOUYIN_CLIENT_KEY/SECRET and DOUYIN_REDIRECT_URI are required")
        params = {
            "client_key": self.client_key,
            "response_type": "code",
            "scope": self.scopes(),
            "redirect_uri": redirect_uri or self.redirect_uri,
            "state": state or generate_state(),
        }
        return OAuthStart(url=f"{AUTHORIZE_URL}?{urlencode(params)}", state=params["state"], provider="douyin", redirect_uri=params["redirect_uri"], scopes=self.scopes())

    def exchange_code(self, code: str, *, code_verifier: str = "", redirect_uri: str | None = None) -> CredentialRecord:
        form = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
        }
        payload = unwrap_douyin(
            self.client.request(
                "POST",
                TOKEN_URL,
                data=urlencode(form).encode("utf-8"),
                content_type="application/x-www-form-urlencoded",
                absolute=True,
            ),
            kind="token",
        )
        data = payload.get("data") if isinstance(payload, dict) else payload
        data = data or payload
        if not isinstance(data, dict) or not data.get("access_token"):
            raise AuthenticationError(f"Douyin token exchange did not return access_token: {payload}")
        return CredentialRecord.from_payload({**data, "provider": "douyin", "scope": data.get("scope") or self.scopes()})

    def refresh(self, refresh_token: str) -> CredentialRecord:
        form = {
            "client_key": self.client_key,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        payload = unwrap_douyin(
            self.client.request(
                "POST",
                REFRESH_URL,
                data=urlencode(form).encode("utf-8"),
                content_type="application/x-www-form-urlencoded",
                absolute=True,
            ),
            kind="refresh",
        )
        data = payload.get("data") if isinstance(payload, dict) else payload
        data = data or payload
        if not isinstance(data, dict) or not data.get("access_token"):
            raise AuthenticationError(f"Douyin refresh did not return access_token: {payload}")
        return CredentialRecord.from_payload({**data, "provider": "douyin"})

    def revoke(self, token: str, *, token_type_hint: str = "access_token") -> RevokeResult:
        return RevokeResult(remote_revoked=False, unsupported=True, reason="Douyin has no public revoke endpoint; delete local credential_ref")

    def validate(self, access_token: str, open_id: str = "") -> dict[str, Any]:
        if not open_id:
            raise AuthenticationError("Douyin userinfo is BLOCKED: open_id is required")
        form = {"access_token": access_token, "open_id": open_id}
        payload = unwrap_douyin(
            self.client.request(
                "POST",
                USERINFO_URL,
                data=urlencode(form).encode("utf-8"),
                content_type="application/x-www-form-urlencoded",
                absolute=True,
            ),
            kind="userinfo",
        )
        return payload if isinstance(payload, dict) else {"raw": payload}
