"""Account manager: connect, verify, enable, disconnect. Tokens never enter business tables."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from social.accounts.models import SocialAccount, enable_account
from social.auth.secrets import RuntimeSecretStore, default_secret_store
from social.providers.resolver import resolve_social_provider

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SocialAccountManager:
    def __init__(self, store: Any | None = None, *, secrets: RuntimeSecretStore | None = None) -> None:
        from integrations.persistence import InMemoryStore

        self.store = store or InMemoryStore()
        self.secrets = secrets or default_secret_store()

    def list_accounts(self, *, platform: str | None = None) -> list[SocialAccount]:
        accounts = list(getattr(self.store, "list_accounts", lambda: [])())
        if platform:
            accounts = [item for item in accounts if item.platform == platform]
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
            if account.status in {"PENDING", "AUTHENTICATING"}:
                account = replace(account, status="AUTHENTICATED", updated_at=_utcnow())
            saved.append(self.save(account))
        return saved[0]

    def verify_account(self, account_id: str, *, adapter: Any | None = None) -> SocialAccount:
        account = self.get_account(account_id)
        implementation = adapter or resolve_social_provider(account.provider).implementation
        verify = getattr(implementation, "verify_capabilities", None)
        capabilities = verify(account.account_id) if callable(verify) else account.capabilities
        from social.accounts.models import SocialProviderCapabilities
        if not isinstance(capabilities, SocialProviderCapabilities):
            capabilities = account.capabilities
        if account.status in {"EXPIRED", "REVOKED", "BLOCKED"}:
            return self.save(replace(account, blocked_reason=account.status, updated_at=_utcnow()))
        verified = replace(
            account,
            status="VERIFIED",
            capabilities=capabilities,
            last_verified_at=_utcnow(),
            updated_at=_utcnow(),
            blocked_reason=None,
        )
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

    def select_verified(self, platform: str) -> SocialAccount:
        usable = [item for item in self.list_accounts(platform=platform) if item.status == "ENABLED"]
        if not usable:
            raise RuntimeError(f"no verified enabled account for platform={platform}")
        return usable[0]

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
            elif account.status != "ENABLED":
                action = "VERIFY"
            rows.append({
                "label": account.label(),
                "status": account.status,
                "action": action,
                "account_id": account.account_id,
            })
        return rows
