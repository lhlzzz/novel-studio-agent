from __future__ import annotations

import os
from typing import Any

from social.auth.credentials import CredentialRecord
from social.auth.oauth import OAuthStart, RevokeResult, generate_state
from social.providers.errors import AuthenticationError, CapabilityUnsupported
from social.providers.xiaohongshu.contract import (
    AUTHORIZE_URL,
    OAUTH_ARCHITECTURE_SUPPORTED,
    OAUTH_CONTRACT_VERIFIED,
    TOKEN_URL,
    WRITE_NOTES_AVAILABLE,
)


class XiaohongshuAuth:
    def available(self) -> bool:
        return bool(os.getenv("XHS_CLIENT_ID", "").strip() and os.getenv("XHS_REDIRECT_URI", "").strip() and os.getenv("XHS_CLIENT_SECRET", "").strip())

    def scopes(self) -> str:
        return os.getenv("XHS_SCOPES", "user_info").strip()

    def architecture_supported(self) -> bool:
        return OAUTH_ARCHITECTURE_SUPPORTED

    def write_notes_available(self) -> bool:
        return WRITE_NOTES_AVAILABLE

    def authorization_url(self, *, state: str | None = None, redirect_uri: str | None = None) -> OAuthStart:
        if not self.available():
            raise AuthenticationError("Xiaohongshu OAuth is BLOCKED_EXTERNAL: XHS_CLIENT_ID/SECRET and XHS_REDIRECT_URI are required")
        if not OAUTH_CONTRACT_VERIFIED or not AUTHORIZE_URL:
            raise AuthenticationError("Xiaohongshu OAuth architecture is supported but token/authorize endpoints are not contract-verified")
        from urllib.parse import urlencode
        params = {
            "response_type": "code",
            "client_id": os.getenv("XHS_CLIENT_ID", "").strip(),
            "redirect_uri": redirect_uri or os.getenv("XHS_REDIRECT_URI", "").strip(),
            "state": state or generate_state(),
            "scope": self.scopes(),
        }
        return OAuthStart(url=f"{AUTHORIZE_URL}?{urlencode(params)}", state=params["state"], provider="xiaohongshu", redirect_uri=params["redirect_uri"], scopes=self.scopes())

    def exchange_code(self, code: str, *, code_verifier: str = "", redirect_uri: str | None = None) -> CredentialRecord:
        if not OAUTH_CONTRACT_VERIFIED or not TOKEN_URL:
            raise AuthenticationError("Xiaohongshu token exchange is BLOCKED_EXTERNAL: official token endpoint is not contract-verified")
        raise CapabilityUnsupported("Xiaohongshu official token exchange is BLOCKED_EXTERNAL until write_notes is live-verified")

    def refresh(self, refresh_token: str) -> CredentialRecord:
        raise CapabilityUnsupported("Xiaohongshu official refresh is NOT_SUPPORTED in handoff-only mode")

    def revoke(self, token: str, *, token_type_hint: str = "access_token") -> RevokeResult:
        return RevokeResult(remote_revoked=False, unsupported=True, reason="no official revoke endpoint")

    def validate(self, access_token: str) -> dict[str, Any]:
        raise CapabilityUnsupported("Xiaohongshu official validate is BLOCKED_EXTERNAL")
