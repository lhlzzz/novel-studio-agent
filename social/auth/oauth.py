"""Shared OAuth contract, PKCE, and CSRF state persistence."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

from social.auth.credentials import CredentialRecord
from social.auth.secrets import RuntimeSecretStore
from social.providers.errors import AuthenticationError, ValidationError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def generate_state() -> str:
    return secrets.token_urlsafe(24)


def states_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(str(left or ""), str(right or ""))


@dataclass(frozen=True)
class OAuthStart:
    url: str
    state: str
    code_verifier: str = ""
    provider: str = ""
    redirect_uri: str = ""
    scopes: str = ""


@dataclass(frozen=True)
class RevokeResult:
    remote_revoked: bool
    unsupported: bool = False
    reason: str | None = None


class OAuthProviderAdapter(Protocol):
    def available(self) -> bool: ...
    def scopes(self) -> str: ...
    def authorization_url(self, *, state: str | None = None, redirect_uri: str | None = None) -> OAuthStart: ...
    def exchange_code(self, code: str, *, code_verifier: str = "", redirect_uri: str | None = None) -> CredentialRecord: ...
    def refresh(self, refresh_token: str) -> CredentialRecord: ...
    def revoke(self, token: str, *, token_type_hint: str = "access_token") -> RevokeResult: ...
    def validate(self, access_token: str) -> dict[str, Any]: ...
    def current_identity(self, access_token: str) -> dict[str, Any]: ...


class OAuthStateStore:
    def __init__(self, secrets: RuntimeSecretStore) -> None:
        self.secrets = secrets

    def save(self, start: OAuthStart, *, ttl_seconds: int = 600) -> str:
        if not start.state or not start.url:
            raise AuthenticationError("OAuth start did not return a real authorization URL and state")
        payload = {
            "provider": start.provider,
            "state": start.state,
            "code_verifier": start.code_verifier,
            "redirect_uri": start.redirect_uri,
            "scopes": start.scopes,
            "url": start.url,
            "expires_at": (utcnow() + timedelta(seconds=ttl_seconds)).isoformat(),
            "access_token": "",
        }
        return self.secrets.put_json(payload, ref=self._ref(start.state))

    def consume(self, provider: str, state: str, *, redirect_uri: str | None = None) -> dict[str, Any]:
        ref = self._ref(state)
        getter = getattr(self.secrets, "get_json", None)
        payload = getter(ref) if callable(getter) else None
        if not payload:
            raise AuthenticationError("OAuth state is missing or expired")
        if not states_equal(str(payload.get("state") or ""), state):
            raise AuthenticationError("OAuth state mismatch")
        if str(payload.get("provider") or "") != provider:
            raise AuthenticationError("OAuth state provider mismatch")
        expected = str(payload.get("redirect_uri") or "")
        if redirect_uri and expected and not states_equal(expected, redirect_uri):
            raise AuthenticationError("OAuth redirect_uri mismatch")
        expires_at = payload.get("expires_at")
        if expires_at:
            expires = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if utcnow() > expires:
                self.secrets.delete(ref)
                raise AuthenticationError("OAuth state expired")
        self.secrets.delete(ref)
        return payload

    @staticmethod
    def _ref(state: str) -> str:
        return f"oauth-state:{state}"


def require_authorization_url(payload: dict[str, str], *, provider: str) -> dict[str, str]:
    if not payload.get("url") or not payload.get("state"):
        raise ValidationError(f"{provider} OAuth is BLOCKED: authorization URL/state must not be empty")
    return payload


def parse_redirect_bind(redirect_uri: str) -> tuple[str, int, str]:
    parsed = urlparse(redirect_uri)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValidationError("OAuth redirect_uri is invalid")
    port = parsed.port or (80 if parsed.scheme == "http" else 443)
    path = parsed.path or "/"
    return parsed.hostname, port, path


def listen_for_callback(redirect_uri: str, *, timeout: int = 300) -> dict[str, str]:
    """One-shot HTTP callback. Returns code/state in memory; never logs them."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    host, port, expected_path = parse_redirect_bind(redirect_uri)
    box: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            incoming = urlparse(self.path)
            if incoming.path != expected_path:
                self.send_response(404)
                self.end_headers()
                return
            query = parse_qs(incoming.query)
            box["code"] = (query.get("code") or [""])[0]
            box["state"] = (query.get("state") or [""])[0]
            box["error"] = (query.get("error") or [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Meiti OAuth callback received. You can close this window.")

    bind_host = host if host in {"127.0.0.1", "localhost", "::1"} else "0.0.0.0"
    try:
        server = HTTPServer((bind_host, port), Handler)
    except OSError as exc:
        raise AuthenticationError(
            f"OAuth callback is BLOCKED_EXTERNAL: cannot bind {bind_host}:{port} for redirect_uri"
        ) from exc
    server.timeout = 1
    deadline = time.time() + max(1, timeout)
    try:
        while time.time() < deadline and not box:
            server.handle_request()
    finally:
        server.server_close()
    if not box:
        raise AuthenticationError("OAuth callback did not arrive")
    return box
