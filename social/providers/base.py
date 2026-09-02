"""Shared native adapter behavior. Platform adapters only encode platform differences."""

from __future__ import annotations

import hashlib
import mimetypes
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from integrations.contracts.distribution import (
    DistributionJob,
    MediaUploadResult,
    ProviderHealth,
    Publication,
    validate_common_payload,
)
from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.auth.secrets import UnconfiguredSecretStore
from social.providers.errors import AuthenticationError, ValidationError
from social.providers.http import SocialHttpClient

NULL_ANALYTICS = {
    "views": None,
    "likes": None,
    "comments": None,
    "shares": None,
    "followers_delta": None,
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class BaseSocialAdapter:
    provider = ""
    platform = ""
    api_base = ""
    claimed: dict[str, bool] = {}

    def __init__(self, *, client: SocialHttpClient | None = None, secrets: Any | None = None) -> None:
        self.client = client or SocialHttpClient(provider=self.provider, base_url=self.api_base)
        self.secrets = secrets if secrets is not None else UnconfiguredSecretStore()
        self._accounts: dict[str, SocialAccount] = {}
        self.rate_limit = self.client.rate_limit

    def _credentials(self, account: SocialAccount | None = None) -> dict[str, Any]:
        from social.providers.errors import TokenExpired
        env_id = os.getenv(f"{self.provider.upper()}_CLIENT_ID", "").strip()
        env_secret = os.getenv(f"{self.provider.upper()}_CLIENT_SECRET", "").strip()
        payload: dict[str, Any] = {}
        if account and account.credential_ref:
            record = self.secrets.get_record(account.credential_ref)
            if record is not None:
                if record.expired():
                    raise TokenExpired(f"{self.provider} access_token expired")
                payload.update(record.to_payload())
            else:
                payload.update(self.secrets.get(account.credential_ref) or {})
        if env_id:
            payload.setdefault("client_id", env_id)
        if env_secret:
            payload.setdefault("client_secret", env_secret)
        token = os.getenv(f"{self.provider.upper()}_ACCESS_TOKEN", "").strip()
        if token:
            payload.setdefault("access_token", token)
        return payload

    def ensure_valid_credentials(self, account: SocialAccount) -> dict[str, Any]:
        """Read-only check. Refresh is owned by SocialAccountManager.refresh_account."""
        return self._credentials(account)

    def _auth_headers(self, account: SocialAccount | None = None) -> dict[str, str]:
        creds = self._credentials(account)
        token = creds.get("access_token") or creds.get("token")
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def health(self) -> ProviderHealth:
        creds = self._credentials()
        if not creds.get("access_token") and not creds.get("client_id"):
            return ProviderHealth(
                provider=self.provider,
                reachable=False,
                authenticated=False,
                account_count=len(self._accounts),
                last_error="credentials missing",
                rate_limit_state=str(self.client.rate_limit.get("remaining")),
            )
        try:
            accounts = self.list_accounts()
            return ProviderHealth(
                provider=self.provider,
                reachable=True,
                authenticated=True,
                account_count=len(accounts),
                rate_limit_state=str(self.client.rate_limit.get("remaining")),
            )
        except Exception as exc:
            return ProviderHealth(
                provider=self.provider,
                reachable=True,
                authenticated=False,
                account_count=0,
                last_error=str(exc),
                rate_limit_state=str(self.client.rate_limit.get("remaining")),
            )

    def authenticate(self, authorization: dict[str, Any] | None = None) -> bool:
        authorization = authorization or {}
        if authorization.get("access_token") or authorization.get("code"):
            return True
        return bool(self._credentials().get("access_token"))

    def list_accounts(self) -> list[SocialAccount]:
        if self._accounts:
            return list(self._accounts.values())
        creds = self._credentials()
        if not creds.get("access_token"):
            return []
        discovered = self._discover_accounts(creds)
        for account in discovered:
            self._accounts[account.account_id] = account
        return discovered

    def _discover_accounts(self, creds: dict[str, Any]) -> list[SocialAccount]:
        raise AuthenticationError(f"{self.provider} account discovery requires a verified OAuth token")

    def get_account(self, account_id: str) -> SocialAccount:
        accounts = {item.account_id: item for item in self.list_accounts()}
        if account_id in accounts:
            return accounts[account_id]
        if account_id in self._accounts:
            return self._accounts[account_id]
        raise KeyError(account_id)

    def get_integration(self, integration_id: str):
        return self.get_account(integration_id).as_integration()

    def list_integrations(self):
        return [item.as_integration() for item in self.list_accounts()]

    def capabilities(self, account_id: str) -> SocialProviderCapabilities:
        try:
            return self.get_account(account_id).capabilities
        except KeyError:
            return SocialProviderCapabilities.from_claimed(self.claimed)

    def get_capabilities(self, integration_id: str) -> Any:
        return self.capabilities(integration_id).to_integration()

    def verify_capabilities(self, account_id: str) -> SocialProviderCapabilities:
        health = self.health()
        if not health.authenticated:
            return SocialProviderCapabilities.from_claimed(self.claimed, verified=False, method="unverified")
        return SocialProviderCapabilities.from_claimed(self.claimed, verified=False, method="probe_required")

    def get_settings(self, integration_id: str) -> dict[str, Any]:
        return {"platform": self.platform, "provider": self.provider, "account_id": integration_id}

    def validate_payload(self, job: DistributionJob) -> list[str]:
        try:
            account = self.get_account(job.account_id)
        except KeyError:
            return [f"unknown social account: {job.account_id}"]
        errors = validate_common_payload(job, account.as_integration())
        errors.extend(self._validate_platform(job, account))
        return errors

    def _validate_platform(self, job: DistributionJob, account: SocialAccount) -> list[str]:
        return []

    def ensure_media(self, job: DistributionJob) -> tuple[DistributionJob, list[MediaUploadResult]]:
        uploaded: list[MediaUploadResult] = []
        metadata = dict(job.variant.metadata or {})
        existing = list(metadata.get("uploaded_media") or [])
        for path in job.variant.media:
            found = next((item for item in existing if item.get("source_path") == path), None)
            if found:
                uploaded.append(
                    MediaUploadResult(
                        source_hash=str(found.get("source_hash") or ""),
                        source_path=path,
                        mime_type=str(found.get("mime_type") or "application/octet-stream"),
                        size=int(found.get("size") or 0),
                        provider=self.provider,
                        remote_id=str(found.get("remote_id") or ""),
                        remote_path=str(found.get("remote_path") or ""),
                        uploaded_at=str(found.get("uploaded_at") or _utcnow()),
                    )
                )
                continue
            uploaded.append(self.upload_media(path, account_id=job.account_id, idempotency_key=job.idempotency_key or job.job_id))
        metadata["uploaded_media"] = [
            {
                "source_hash": item.source_hash,
                "source_path": item.source_path,
                "mime_type": item.mime_type,
                "size": item.size,
                "remote_id": item.remote_id,
                "remote_path": item.remote_path,
                "uploaded_at": item.uploaded_at,
            }
            for item in uploaded
        ]
        variant = replace(job.variant, metadata=metadata)
        return replace(job, variant=variant), uploaded

    def upload_media(self, source_path: str, *, account_id: str = "", idempotency_key: str = "") -> MediaUploadResult:
        path = Path(source_path)
        if not path.exists():
            raise ValidationError(f"media file does not exist: {path}")
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        remote = self._upload_bytes(data, mime_type=mime_type, filename=path.name, account_id=account_id, idempotency_key=idempotency_key)
        return MediaUploadResult(
            source_hash=digest,
            source_path=str(path),
            mime_type=mime_type,
            size=len(data),
            provider=self.provider,
            remote_id=str(remote.get("id") or remote.get("media_id") or ""),
            remote_path=str(remote.get("url") or remote.get("path") or remote.get("upload_token") or ""),
            uploaded_at=_utcnow(),
            account_id=account_id,
        )

    def _upload_bytes(self, data: bytes, *, mime_type: str, filename: str, account_id: str, idempotency_key: str) -> dict[str, Any]:
        raise ValidationError(f"{self.provider} media upload is BLOCKED until credentials and a verified media contract exist")

    def publish(self, job: DistributionJob) -> dict[str, Any]:
        raise ValidationError(f"{self.provider} publish is BLOCKED until a verified account exists")

    def schedule(self, job: DistributionJob) -> dict[str, Any]:
        if not self.claimed.get("schedule"):
            raise ValidationError(f"{self.provider} native schedule is unsupported; use Meiti scheduler")
        return self.publish(job)

    def get_status(self, provider_post_id: str, *, provider_object_type: str = "") -> dict[str, Any]:
        raise ValidationError(f"{self.provider} status is BLOCKED until credentials exist")

    def delete(self, provider_post_id: str) -> dict[str, Any]:
        raise ValidationError(f"{self.provider} delete is BLOCKED until credentials exist")

    def cancel(self, provider_post_id: str) -> dict[str, Any]:
        return self.delete(provider_post_id)

    def analytics(self, publication: Publication) -> dict[str, Any | None]:
        return dict(NULL_ANALYTICS)

    def get_analytics(self, provider_post_id: str) -> dict[str, Any | None]:
        publication = Publication(
            distribution_job_id=provider_post_id,
            account_id="",
            provider=self.provider,
            provider_post_id=provider_post_id,
            platform=self.platform,
        )
        return self.analytics(publication)

    def refresh(self, account: SocialAccount) -> SocialAccount:
        raise AuthenticationError(f"{self.provider} refresh must go through SocialAccountManager.refresh_account")

    def revoke(self, account: SocialAccount) -> None:
        auth = getattr(self, "auth", None)
        revoke = getattr(auth, "revoke", None)
        if not callable(revoke):
            from social.auth.oauth import RevokeResult
            return RevokeResult(remote_revoked=False, unsupported=True, reason=f"{self.provider} has no revoke endpoint")
        creds = self._credentials(account)
        token = str(creds.get("access_token") or "")
        return revoke(token)


class BaseCNAdapter(BaseSocialAdapter):
    region = "cn"

    def schedule(self, job: DistributionJob) -> dict[str, Any]:
        raise ValidationError(f"{self.provider} native schedule is unsupported; use Meiti scheduler")
