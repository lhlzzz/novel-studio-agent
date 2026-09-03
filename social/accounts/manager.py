"""SocialAccountManager is the only owner of account connect/verify/enable/refresh/disconnect."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from social.accounts.models import (
    ACCOUNT_TRANSITIONS,
    SocialAccount,
    SocialProviderCapabilities,
    enable_account,
    transition_account,
)
from social.auth.oauth import OAuthStart, OAuthStateStore
from social.auth.secrets import RuntimeSecretStore, secret_id
from social.providers.errors import AuthenticationError, CapabilityUnsupported
from social.providers.resolver import resolve_social_provider


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SocialAccountManager:
    def __init__(self, store: Any, *, secrets: RuntimeSecretStore, oauth_states: OAuthStateStore | None = None) -> None:
        if store is None:
            raise ValueError("SocialAccountManager requires an explicit store")
        if secrets is None:
            raise ValueError("SocialAccountManager requires an explicit secret store")
        self.store = store
        self.secrets = secrets
        self.oauth_states = oauth_states or OAuthStateStore(secrets)

    def list_accounts(self, *, platform: str | None = None, provider: str | None = None, region: str | None = None) -> list[SocialAccount]:
        accounts = list(self.store.list_accounts())
        if platform:
            accounts = [item for item in accounts if item.platform == platform]
        if provider:
            accounts = [item for item in accounts if item.provider == provider]
        if region:
            accounts = [item for item in accounts if item.region == region]
        return accounts

    def get_account(self, account_id: str) -> SocialAccount:
        account = self.store.get_account(account_id)
        if account is None:
            raise KeyError(account_id)
        return account

    def save(self, account: SocialAccount) -> SocialAccount:
        return self.store.save_account(replace(account, updated_at=_utcnow()))

    def start_oauth(self, provider: str, *, redirect_uri: str | None = None, adapter: Any | None = None) -> OAuthStart:
        implementation = adapter or resolve_social_provider(provider).implementation
        auth = getattr(implementation, "auth", None)
        if auth is None or not callable(getattr(auth, "authorization_url", None)):
            raise CapabilityUnsupported(f"{provider} OAuth is NOT_SUPPORTED")
        start = auth.authorization_url(redirect_uri=redirect_uri)
        if not start.state or not start.url:
            raise AuthenticationError(f"{provider} OAuth did not return a real authorization URL and state")
        self.oauth_states.save(start)
        return start

    def complete_oauth(self, provider: str, *, code: str, state: str, adapter: Any | None = None) -> SocialAccount:
        implementation = adapter or resolve_social_provider(provider).implementation
        auth = getattr(implementation, "auth", None)
        if auth is None or not callable(getattr(auth, "exchange_code", None)):
            raise CapabilityUnsupported(f"{provider} OAuth exchange is NOT_SUPPORTED")
        expected_redirect = str(getattr(auth, "redirect_uri", "") or "") or None
        payload = self.oauth_states.consume(provider, state, redirect_uri=expected_redirect)
        record = auth.exchange_code(
            code,
            code_verifier=str(payload.get("code_verifier") or ""),
            redirect_uri=str(payload.get("redirect_uri") or "") or None,
        )
        account_key = record.provider_account_id or record.provider or provider
        ref = self.secrets.put(record, ref=secret_id(provider, account_key))
        setattr(implementation, "_credential_ref", ref)
        if hasattr(implementation, "secrets") and implementation.secrets is None:
            implementation.secrets = self.secrets
        return self.connect_account(provider, authorization={"credential_ref": ref}, adapter=implementation)

    def connect_account(self, provider: str, *, authorization: dict[str, Any] | None = None, adapter: Any | None = None) -> SocialAccount:
        implementation = adapter or resolve_social_provider(provider).implementation
        authorization = dict(authorization or {})
        if authorization.get("code") and authorization.get("state"):
            return self.complete_oauth(provider, code=str(authorization["code"]), state=str(authorization["state"]), adapter=implementation)
        if authorization.get("code") and not authorization.get("state"):
            raise AuthenticationError(f"{provider} OAuth callback is BLOCKED: state is required")
        if hasattr(implementation, "secrets") and getattr(implementation, "secrets", None) is None:
            implementation.secrets = self.secrets
        authenticate = getattr(implementation, "authenticate", None)
        if callable(authenticate):
            connected = authenticate(authorization) if authorization else authenticate()
            if not connected:
                raise RuntimeError(f"{provider} authentication failed")
        discovered = list(implementation.list_accounts())
        if not discovered:
            raise RuntimeError(f"{provider} returned no accounts")
        saved: list[SocialAccount] = []
        for item in discovered:
            if isinstance(item, SocialAccount):
                account = item
            else:
                account = SocialAccount(
                    account_id=getattr(item, "id"),
                    provider=provider,
                    platform=getattr(item, "platform", provider),
                    username=getattr(item, "account_name", "") or getattr(item, "username", ""),
                    display_name=getattr(item, "account_name", ""),
                    status="AUTHENTICATED",
                )
            if account.provider == "xiaohongshu" or account.status in {"HANDOFF_READY", "TARGET_ONLY"}:
                status = "HANDOFF_READY"
            elif account.status == "IDENTITY_UNVERIFIED":
                status = "IDENTITY_UNVERIFIED"
            else:
                status = "AUTHENTICATED"
            credential_ref = account.credential_ref or str(authorization.get("credential_ref") or getattr(implementation, "_credential_ref", "") or "")
            account = replace(
                account,
                status=status,
                credential_ref=credential_ref,
                updated_at=_utcnow(),
                blocked_reason=None,
            )
            saved.append(self.save(account))
        return saved[0]

    def verify_account(self, account_id: str, *, adapter: Any | None = None) -> SocialAccount:
        account = self.get_account(account_id)
        implementation = adapter or resolve_social_provider(account.provider).implementation
        if account.status in {"EXPIRED", "REVOKED", "BLOCKED", "IDENTITY_UNVERIFIED"}:
            return self.save(replace(account, blocked_reason=account.status, updated_at=_utcnow()))
        if account.status in {"HANDOFF_READY", "TARGET_ONLY"}:
            verify = getattr(implementation, "verify_capabilities", None)
            capabilities = verify(account.account_id) if callable(verify) else account.capabilities
            if not isinstance(capabilities, SocialProviderCapabilities):
                capabilities = account.capabilities
            handoff = capabilities.records.get("handoff")
            if handoff is None or not handoff.allowed:
                return self.save(replace(account, capabilities=capabilities, blocked_reason="handoff capability unverified"))
            return self.save(replace(account, capabilities=capabilities, last_verified_at=_utcnow(), blocked_reason=None, status="HANDOFF_READY"))
        if account.status == "AUTHENTICATED":
            account = self.save(transition_account(account, "VERIFYING"))
        elif account.status not in {"VERIFYING", "VERIFIED", "ENABLED", "DEGRADED"}:
            raise RuntimeError(f"{account.status} accounts cannot be verified")
        verify = getattr(implementation, "verify_capabilities", None)
        try:
            capabilities = verify(account.account_id) if callable(verify) else account.capabilities
        except Exception as exc:
            blocked = transition_account(account, "BLOCKED", blocked_reason=str(exc), capabilities=account.capabilities)
            return self.save(blocked)
        if not isinstance(capabilities, SocialProviderCapabilities):
            capabilities = account.capabilities
        publish = capabilities.records.get("publish") or capabilities.records.get("handoff")
        listing = capabilities.records.get("listing")
        usable = bool((publish and publish.allowed) or (listing and listing.allowed) or capabilities.verified("handoff"))
        if not usable:
            if account.status == "VERIFYING":
                return self.save(transition_account(account, "AUTHENTICATED", blocked_reason="capability verification failed", capabilities=capabilities))
            return self.save(replace(account, capabilities=capabilities, blocked_reason="capability verification failed"))
        if account.status == "VERIFYING":
            verified = transition_account(
                account,
                "VERIFIED",
                capabilities=capabilities,
                last_verified_at=_utcnow(),
                blocked_reason=None,
            )
        else:
            verified = replace(account, capabilities=capabilities, last_verified_at=_utcnow(), blocked_reason=None)
            if account.status not in {"VERIFIED", "ENABLED"}:
                verified = replace(verified, status="VERIFIED")
        return self.save(verified)

    def enable_account(self, account_id: str) -> SocialAccount:
        account = self.get_account(account_id)
        return self.save(enable_account(account))

    def get_credentials(self, account_id: str):
        """Read-only credential lookup. Does not refresh."""
        account = self.get_account(account_id)
        if not account.credential_ref:
            return None
        return self.secrets.get_record(account.credential_ref)

    def revoke_account(self, account_id: str, *, adapter: Any | None = None) -> SocialAccount:
        return self.disconnect_account(account_id, adapter=adapter)

    def refresh_account(self, account_id: str, *, adapter: Any | None = None) -> SocialAccount:
        account = self.get_account(account_id)
        if account.provider == "xiaohongshu" or account.status in {"HANDOFF_READY", "TARGET_ONLY"}:
            raise CapabilityUnsupported("Xiaohongshu refresh is NOT_SUPPORTED")
        implementation = adapter or resolve_social_provider(account.provider).implementation
        auth = getattr(implementation, "auth", None)
        refresh = getattr(auth, "refresh", None)
        if not callable(refresh):
            return self.save(self._to_expired(account, "refresh unsupported"))
        if not account.credential_ref:
            return self.save(self._to_expired(account, "credential_ref missing"))
        record = self.secrets.get_record(account.credential_ref)
        if record is None or not record.refresh_token:
            return self.save(self._to_expired(account, "refresh_token missing"))
        previous = account.status
        try:
            if "REFRESHING" in ACCOUNT_TRANSITIONS.get(account.status, set()):
                account = self.save(transition_account(account, "REFRESHING"))
            new_record = refresh(record.refresh_token)
        except Exception as exc:
            return self.save(self._to_expired(account, str(exc)))
        stored = self.secrets.replace(account.credential_ref, new_record)
        current = self.save(replace(
            account,
            provider_account_id=stored.provider_account_id or account.provider_account_id,
            blocked_reason=None,
            updated_at=_utcnow(),
        ))
        if current.status == "REFRESHING":
            current = self.save(transition_account(current, "VERIFYING"))
        elif current.status in {"VERIFIED", "AUTHENTICATED"}:
            current = self.save(transition_account(current, "VERIFYING"))
        try:
            verified = self.verify_account(account_id, adapter=implementation)
        except Exception as exc:
            return self.save(transition_account(current, "BLOCKED", blocked_reason=str(exc)))
        if verified.status == "VERIFIED" and previous == "ENABLED":
            return self.enable_account(verified.account_id)
        return verified

    def disconnect_account(self, account_id: str, *, adapter: Any | None = None) -> SocialAccount:
        account = self.get_account(account_id)
        implementation = adapter or resolve_social_provider(account.provider).implementation
        revoke_attempted = False
        remote_revoked = False
        remote_revoke_supported = False
        error = None
        token = ""
        if account.credential_ref:
            record = self.secrets.get_record(account.credential_ref)
            token = record.access_token if record is not None else ""
        auth = getattr(implementation, "auth", None)
        revoke = getattr(auth, "revoke", None) or getattr(implementation, "revoke", None)
        if callable(revoke):
            revoke_attempted = True
            try:
                result = revoke(token or account) if token else revoke(account)
                unsupported = bool(getattr(result, "unsupported", False))
                remote_revoke_supported = not unsupported
                remote_revoked = bool(getattr(result, "remote_revoked", False))
            except Exception as exc:
                error = str(exc)
                remote_revoke_supported = True
        if account.credential_ref:
            self.secrets.delete(account.credential_ref)
        revoked = replace(
            account,
            status="REVOKED" if account.status == "REVOKED" or "REVOKED" in ACCOUNT_TRANSITIONS.get(account.status, set()) else account.status,
            credential_ref="",
            updated_at=_utcnow(),
            revoke_attempted=revoke_attempted,
            remote_revoked=remote_revoked,
            remote_revoke_supported=remote_revoke_supported,
            revoke_error=error,
        )
        if revoked.status != "REVOKED" and "REVOKED" in ACCOUNT_TRANSITIONS.get(account.status, set()):
            revoked = transition_account(
                account,
                "REVOKED",
                credential_ref="",
                revoke_attempted=revoke_attempted,
                remote_revoked=remote_revoked,
                remote_revoke_supported=remote_revoke_supported,
                revoke_error=error,
            )
        return self.save(revoked)

    def select_enabled(
        self,
        platform: str,
        *,
        account_id: str | None = None,
        provider: str | None = None,
        region: str | None = None,
        capability: str = "publish",
    ) -> SocialAccount:
        allowed = {"ENABLED"}
        if capability == "handoff" or platform in {"xiaohongshu", "xhs"}:
            allowed = {"HANDOFF_READY"}
            capability = "handoff"
        if account_id:
            account = self.get_account(account_id)
            if account.status not in allowed:
                raise RuntimeError(f"account {account_id} is not {sorted(allowed)}")
            if account.platform != platform and account.provider != platform:
                raise RuntimeError(f"account {account_id} is not on platform={platform}")
            return self._require_healthy(account, capability)
        usable = []
        for item in self.list_accounts(platform=platform, provider=provider, region=region):
            if item.status not in allowed:
                continue
            if not self._credential_healthy(item):
                continue
            if capability and not item.capabilities.verified(capability) and not item.capabilities.verified("handoff"):
                continue
            usable.append(item)
        if not usable:
            raise RuntimeError(f"no verified enabled account for platform={platform}")
        if len(usable) > 1:
            raise RuntimeError(f"multiple ENABLED accounts for platform={platform}; pass explicit account_id")
        return usable[0]

    def select_verified(self, platform: str, *, account_id: str | None = None) -> SocialAccount:
        capability = "handoff" if platform in {"xiaohongshu", "xhs"} else "publish"
        return self.select_enabled(platform, account_id=account_id, capability=capability)

    def _credential_healthy(self, account: SocialAccount) -> bool:
        if account.status in {"HANDOFF_READY", "TARGET_ONLY"} or account.capabilities.verified("handoff"):
            return True
        if not account.credential_ref:
            return False
        payload = self.secrets.get_record(account.credential_ref)
        if payload is None:
            return False
        if not payload.access_token:
            return False
        if payload.expired():
            return False
        return True

    def _require_healthy(self, account: SocialAccount, capability: str) -> SocialAccount:
        if not self._credential_healthy(account):
            raise RuntimeError(f"account {account.account_id} credential is unusable")
        if capability and not account.capabilities.verified(capability) and not account.capabilities.verified("handoff"):
            raise RuntimeError(f"account {account.account_id} capability {capability} is unverified")
        return account

    def _to_expired(self, account: SocialAccount, reason: str) -> SocialAccount:
        if account.status == "EXPIRED":
            return replace(account, blocked_reason=reason, updated_at=_utcnow())
        if "EXPIRED" in ACCOUNT_TRANSITIONS.get(account.status, set()):
            return transition_account(account, "EXPIRED", blocked_reason=reason)
        return replace(account, blocked_reason=reason, updated_at=_utcnow())

    def doctor_rows(self) -> list[dict[str, str]]:
        rows = []
        for account in self.list_accounts():
            action = "OK"
            if account.status in {"EXPIRED", "REVOKED"}:
                action = "RE-AUTHENTICATE"
            elif account.status == "BLOCKED":
                action = account.blocked_reason or "BLOCKED"
            elif account.status == "VERIFIED":
                action = "ENABLE"
            elif account.status == "HANDOFF_READY":
                action = "HANDOFF"
            elif account.status == "IDENTITY_UNVERIFIED":
                action = "JUSHITA"
            elif account.status == "VERIFYING":
                action = "VERIFY"
            elif account.status != "ENABLED":
                action = "VERIFY"
            rows.append({
                "label": account.label(),
                "status": account.status,
                "action": action,
                "account_id": account.account_id,
                "provider": account.provider,
            })
        return rows
