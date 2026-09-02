from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

from social.auth.credentials import CredentialRecord
from social.auth.oauth import OAuthStart, RevokeResult, generate_state
from social.providers.errors import AuthenticationError
from social.providers.http import SocialHttpClient
from social.providers.xianyu.contract import AUTHORIZE_URL, TOKEN_URL


class XianyuAuth:
    def __init__(self, *, client: SocialHttpClient | None = None) -> None:
        self.app_key = os.getenv("XIANYU_APP_KEY", "").strip() or os.getenv("XIANYU_CLIENT_ID", "").strip()
        self.app_secret = os.getenv("XIANYU_APP_SECRET", "").strip() or os.getenv("XIANYU_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.getenv("XIANYU_REDIRECT_URI", "").strip()
        self.client = client or SocialHttpClient(provider="xianyu", base_url="https://eco.taobao.com")

    def available(self) -> bool:
        return bool(self.app_key and self.app_secret and self.redirect_uri)

    def scopes(self) -> str:
        return os.getenv("XIANYU_SCOPES", "idle_isv")

    def authorization_url(self, *, state: str | None = None, redirect_uri: str | None = None) -> OAuthStart:
        if not self.available():
            raise AuthenticationError("Xianyu OAuth is BLOCKED: XIANYU_APP_KEY/SECRET and XIANYU_REDIRECT_URI are required")
        params = {
            "response_type": "code",
            "client_id": self.app_key,
            "redirect_uri": redirect_uri or self.redirect_uri,
            "state": state or generate_state(),
        }
        return OAuthStart(url=f"{AUTHORIZE_URL}?{urlencode(params)}", state=params["state"], provider="xianyu", redirect_uri=params["redirect_uri"], scopes=self.scopes())

    def exchange_code(self, code: str, *, code_verifier: str = "", redirect_uri: str | None = None) -> CredentialRecord:
        from urllib.parse import urlencode as enc
        body = enc({
            "grant_type": "authorization_code",
            "client_id": self.app_key,
            "client_secret": self.app_secret,
            "code": code,
            "redirect_uri": redirect_uri or self.redirect_uri,
        }).encode("utf-8")
        payload = self.client.request("POST", TOKEN_URL, headers={"Content-Type": "application/x-www-form-urlencoded"}, data=body, absolute=True)
        data = payload if isinstance(payload, dict) else {}
        token = data.get("access_token") or data.get("accessToken")
        if not token:
            raise AuthenticationError(f"Xianyu token exchange did not return access_token: {payload}")
        return CredentialRecord.from_payload({
            "provider": "xianyu",
            "access_token": token,
            "refresh_token": data.get("refresh_token") or data.get("refreshToken"),
            "expires_in": data.get("expires_in") or data.get("expiresIn"),
            "provider_account_id": data.get("taobao_user_id") or data.get("uid") or "",
            "scope": data.get("scope") or self.scopes(),
        })

    def refresh(self, refresh_token: str) -> CredentialRecord:
        from urllib.parse import urlencode as enc
        body = enc({
            "grant_type": "refresh_token",
            "client_id": self.app_key,
            "client_secret": self.app_secret,
            "refresh_token": refresh_token,
        }).encode("utf-8")
        payload = self.client.request("POST", TOKEN_URL, headers={"Content-Type": "application/x-www-form-urlencoded"}, data=body, absolute=True)
        data = payload if isinstance(payload, dict) else {}
        token = data.get("access_token") or data.get("accessToken")
        if not token:
            raise AuthenticationError(f"Xianyu refresh did not return access_token: {payload}")
        return CredentialRecord.from_payload({**data, "provider": "xianyu", "access_token": token})

    def revoke(self, token: str, *, token_type_hint: str = "access_token") -> RevokeResult:
        return RevokeResult(remote_revoked=False, unsupported=True, reason="Xianyu revoke is account disconnect")

    def validate(self, access_token: str) -> dict[str, Any]:
        return {"access_token": bool(access_token)}
