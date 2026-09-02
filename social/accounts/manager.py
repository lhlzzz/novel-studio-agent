"""Account manager: connect, verify, enable, disconnect. Tokens never enter business tables."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from social.accounts.models import SocialAccount, SocialProviderCapabilities, enable_account, transition_account
from social.auth.secrets import RuntimeSecretStore, default_secret_store
from social.providers.resolver import resolve_social_provider


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SocialAccountManager:
    def __init__(self, store: Any | None = None, *, secrets: RuntimeSecretStore | None = None) -> None:
        from integrations.persistence import InMemoryStore

        self.store = store or InMemoryStore()
        self.secrets = secrets or default_secret_store()

    def list_accounts(self, *, platform: str | None = None, provider: str | None = None, region: str | None = None) -> list[SocialAccount]:
        accounts = list(getattr(self.store, "list_accounts", lambda: [])())
        if platform:
            accounts = [item for item in accounts if item.platform == platform]
        if provider:
            accounts = [item for item in accounts if item.provider == provider]
        if region:
            accounts = [item for item in accounts if item.region == region]
        return accounts

    def get_account(self, account_id: str) -> SocialAccount:
        account = getattr(self.store, "get_account", lambda _id: None)(account_id)
        if account is None:
            raise KeyError(account_id)
        return account

    def save(self, account: SocialAccount) -> SocialAccount:
        return self.store.save_account(replace(account, updated_at=_utcnow()))

    def connect_account(self, provider: str, *, authorization: dict[str, Any] | None = None, adapter: Any | None = None) -> SocialAccount:
        implementation = adapter or resolve_social_provider(provider).implementation
        authorization = authorization or {}
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
            account = item if isinstance(item, SocialAccount) else SocialAccount(
                account_id=getattr(item, "id"),
                provider=provider,
                platform=getattr(item, "platform", provider),
                username=getattr(item, "account_name", "") or getattr(item, "username", ""),
                display_name=getattr(item, "account_name", ""),
                status="AUTHENTICATED",
            )
            account = replace(account, status="AUTHENTICATED", updated_at=_utcnow(), blocked_reason=None)
            saved.append(self.save(account))
        return saved[0]

    def verify_account(self, account_id: str, *, adapter: Any | None = None) -> SocialAccount:
        account = self.get_account(account_id)
        implementation = adapter or resolve_social_provider(account.provider).implementation
        if account.status in {"EXPIRED", "REVOKED", "BLOCKED"}:
            return self.save(replace(account, blocked_reason=account.status, updated_at=_utcnow()))
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
            blocked = transition_account(
                account,
                "BLOCKED" if account.status == "VERIFYING" else account.status,
                blocked_reason="capability verification failed",
                capabilities=capabilities,
            ) if account.status == "VERIFYING" else replace(account, capabilities=capabilities, blocked_reason="capability verification failed")
            if account.status == "VERIFYING":
                blocked = self.save(transition_account(account, "AUTHENTICATED", blocked_reason="capability verification failed", capabilities=capabilities))
                return blocked
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

    def refresh_account(self, account_id: str, *, adapter: Any | None = None) -> SocialAccount:
        account = self.get_account(account_id)
        implementation = adapter or resolve_social_provider(account.provider).implementation
        refresh = getattr(implementation, "refresh", None)
        if not callable(refresh):
            return self.save(replace(account, status="EXPIRED", updated_at=_utcnow(), blocked_reason="refresh unsupported"))
        try:
            refresh(account)
        except Exception as exc:
            return self.save(replace(account, status="EXPIRED", updated_at=_utcnow(), blocked_reason=str(exc)))
        if account.status in {"ENABLED", "VERIFIED", "DEGRADED"}:
            account = self.save(replace(self.get_account(account_id), status="VERIFYING" if self.get_account(account_id).status != "VERIFYING" else self.get_account(account_id).status))
        current = self.get_account(account_id)
        if current.status in {"ENABLED", "VERIFIED", "DEGRADED", "AUTHENTICATED"}:
            if current.status != "VERIFYING" and current.status in {"ENABLED", "VERIFIED", "DEGRADED"}:
                try:
                    current = self.save(transition_account(replace(current, status="VERIFIED") if current.status == "ENABLED" else current, "VERIFYING") if current.status == "VERIFIED" else current)
                except Exception:
                    pass
        return self.verify_account(account_id, adapter=implementation)

    def disconnect_account(self, account_id: str, *, adapter: Any | None = None) -> SocialAccount:
        account = self.get_account(account_id)
        if account.credential_ref:
            self.secrets.delete(account.credential_ref)
        implementation = adapter or resolve_social_provider(account.provider).implementation
        revoke = getattr(implementation, "revoke", None)
        if callable(revoke):
            try:
                revoke(account)
            except Exception:
                pass
        return self.save(replace(account, status="REVOKED", credential_ref="", updated_at=_utcnow()))

    def select_enabled(
        self,
        platform: str,
        *,
        account_id: str | None = None,
        provider: str | None = None,
        region: str | None = None,
        capability: str = "publish",
    ) -> SocialAccount:
        if account_id:
            account = self.get_account(account_id)
            if account.status != "ENABLED":
                raise RuntimeError(f"account {account_id} is not ENABLED")
            if account.platform != platform and account.provider != platform:
                raise RuntimeError(f"account {account_id} is not on platform={platform}")
            return self._require_healthy(account, capability)
        usable = []
        for item in self.list_accounts(platform=platform, provider=provider, region=region):
            if item.status != "ENABLED":
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
        return self.select_enabled(platform, account_id=account_id)

    def _credential_healthy(self, account: SocialAccount) -> bool:
        if account.capabilities.verified("handoff"):
            return True
        if not account.credential_ref:
            return False
        record = getattr(self.secrets, "get_record", None)
        payload = record(account.credential_ref) if callable(record) else self.secrets.get(account.credential_ref)
        if payload is None:
            return False
        token = getattr(payload, "access_token", None)
        if token is None and isinstance(payload, dict):
            token = payload.get("access_token") or payload.get("token")
        if not token:
            return False
        expired = getattr(payload, "expired", None)
        if callable(expired) and expired():
            return False
        return True

    def _require_healthy(self, account: SocialAccount, capability: str) -> SocialAccount:
        if not self._credential_healthy(account):
            raise RuntimeError(f"account {account.account_id} credential is unusable")
        if capability and not account.capabilities.verified(capability) and not account.capabilities.verified("handoff"):
            raise RuntimeError(f"account {account.account_id} capability {capability} is unverified")
        return account

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
            elif account.status == "VERIFYING":
                action = "VERIFY"
            elif account.status != "ENABLED":
                action = "VERIFY"
            rows.append({
                "label": account.label(),
                "status": account.status,
                "action": action,
                "account_id": account.account_id,
            })
        return rows
