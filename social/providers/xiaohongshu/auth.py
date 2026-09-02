from __future__ import annotations

import os
from typing import Any

from social.auth.credentials import CredentialRecord
from social.auth.oauth import OAuthStart, RevokeResult, generate_state
from social.providers.errors import AuthenticationError, CapabilityUnsupported


class XiaohongshuAuth:
    def available(self) -> bool:
        return bool(os.getenv("XHS_CLIENT_ID", "").strip() and os.getenv("XHS_REDIRECT_URI", "").strip())

    def scopes(self) -> str:
        return os.getenv("XHS_SCOPES", "").strip()

    def authorization_url(self, *, state: str | None = None, redirect_uri: str | None = None) -> OAuthStart:
        if not self.available():
            raise AuthenticationError("Xiaohongshu OAuth is BLOCKED: official server OAuth is not currently available")
        raise CapabilityUnsupported("Xiaohongshu official OAuth/server publish is BLOCKED until the official server contract is restored")

    def exchange_code(self, code: str, *, code_verifier: str = "", redirect_uri: str | None = None) -> CredentialRecord:
        raise CapabilityUnsupported("Xiaohongshu official token exchange is BLOCKED")

    def refresh(self, refresh_token: str) -> CredentialRecord:
        raise CapabilityUnsupported("Xiaohongshu official refresh is BLOCKED")

    def revoke(self, token: str, *, token_type_hint: str = "access_token") -> RevokeResult:
        return RevokeResult(remote_revoked=False, unsupported=True, reason="no official revoke endpoint")

    def validate(self, access_token: str) -> dict[str, Any]:
        raise CapabilityUnsupported("Xiaohongshu official validate is BLOCKED")
