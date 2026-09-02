from __future__ import annotations

import os
from typing import Any

from integrations.contracts.distribution import CapabilityRecord
from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.auth.credentials import CredentialRecord
from social.media_policy import validate_job
from social.providers.base import BaseCNAdapter
from social.providers.errors import AuthenticationError, MediaUploadError, PublishError, ValidationError
from social.providers.kuaishou.auth import KuaishouAuth
from social.providers.kuaishou.capabilities import CLAIMED, REQUIRED_SCOPES
from social.providers.kuaishou.client import KuaishouClient
from social.providers.kuaishou.schemas import map_status, photo_from_payload, user_from_payload


class KuaishouAdapter(BaseCNAdapter):
    provider = "kuaishou"
    platform = "kuaishou"
    api_base = "https://open.kuaishou.com"
    claimed = CLAIMED

    def __init__(self, *, client: KuaishouClient | None = None, secrets: Any | None = None) -> None:
        http = None if client is None else client.http
        super().__init__(client=http, secrets=secrets)
        self.ks_client = client or KuaishouClient(http=self.client)
        self.auth = KuaishouAuth(client=self.client)
        self.app_id = self.auth.app_id

    def authenticate(self, authorization: dict[str, Any] | None = None) -> bool:
        authorization = authorization or {}
        if authorization.get("code"):
            record = self.auth.exchange_code(str(authorization["code"]))
            self._credential_ref = self.secrets.put(record)
            return True
        if authorization.get("access_token"):
            self._credential_ref = self.secrets.put(CredentialRecord.from_payload({**authorization, "provider": "kuaishou"}))
            return True
        return super().authenticate(authorization)

    def _discover_accounts(self, creds: dict[str, Any]) -> list[SocialAccount]:
        token = str(creds.get("access_token") or "")
        if not token:
            raise AuthenticationError("Kuaishou account discovery is BLOCKED: access token missing")
        payload = self.ks_client.user_info(self.app_id, token)
        user = user_from_payload(payload if isinstance(payload, dict) else {})
        if not user.user_id:
            raise AuthenticationError("Kuaishou user_info did not return user_id")
        return [SocialAccount(
            account_id=f"kuaishou:{user.user_id}",
            provider="kuaishou",
            platform="kuaishou",
            username=user.name,
            display_name=user.name,
            avatar_url=user.avatar,
            status="AUTHENTICATED",
            region="cn",
            capabilities=SocialProviderCapabilities.from_claimed(CLAIMED),
            provider_account_id=user.user_id,
            credential_ref=getattr(self, "_credential_ref", "") or "",
        )]

    def verify_capabilities(self, account_id: str) -> SocialProviderCapabilities:
        account = self.get_account(account_id)
        creds = self._credentials(account)
        token = str(creds.get("access_token") or "")
        if not token:
            return SocialProviderCapabilities.from_claimed(CLAIMED, verified=False, method="unverified")
        try:
            payload = self.ks_client.user_info(self.app_id, token)
            user = user_from_payload(payload if isinstance(payload, dict) else {})
            if not user.user_id:
                raise AuthenticationError("user_id missing")
        except Exception:
            return SocialProviderCapabilities.from_claimed(CLAIMED, verified=False, method="unverified")
        record = self.secrets.get_record(account.credential_ref) if account.credential_ref else None
        scopes = (record.scopes or record.scope or "") if record is not None else ""
        scope_ok = all(name in scopes.replace(",", " ").split() for name in REQUIRED_SCOPES) if scopes else False
        method = "runtime_probe"
        records = {
            name: CapabilityRecord(name=name, supported=bool(value), verified=bool(value and name != "publish"), method=method)
            for name, value in CLAIMED.items()
        }
        records["publish"] = CapabilityRecord(name="publish", supported=True, verified=scope_ok, method=method if scope_ok else "scope_missing")
        records["video"] = CapabilityRecord(name="video", supported=True, verified=True, method=method)
        records["media_upload"] = CapabilityRecord(name="media_upload", supported=True, verified=True, method=method)
        records["analytics"] = CapabilityRecord(name="analytics", supported=True, verified=True, method=method)
        return SocialProviderCapabilities.from_records(records)

    def _validate_platform(self, job, account) -> list[str]:
        errors = validate_job(job, platform="kuaishou")
        if not job.variant.media:
            errors.append("kuaishou publish requires a video")
        return errors

    def _upload_bytes(self, data: bytes, *, mime_type: str, filename: str, account_id: str, idempotency_key: str) -> dict[str, Any]:
        account = self.get_account(account_id) if account_id else None
        creds = self._credentials(account)
        token = str(creds.get("access_token") or "")
        if not token:
            raise AuthenticationError("Kuaishou upload is BLOCKED: access token missing")
        started = self.ks_client.start_upload(self.app_id, token, account_id=account_id, idempotency_key=idempotency_key)
        data_obj = started.get("data") if isinstance(started, dict) and isinstance(started.get("data"), dict) else started
        upload_token = str((data_obj or {}).get("upload_token") or (started or {}).get("upload_token") or "")
        endpoint = str((data_obj or {}).get("endpoint") or (started or {}).get("endpoint") or "")
        if not upload_token or not endpoint:
            raise MediaUploadError("Kuaishou start_upload did not return upload_token and endpoint")
        if endpoint.startswith("http://") and "kuaishou" not in endpoint:
            raise MediaUploadError("Kuaishou upload endpoint must be the runtime value from start_upload")
        if len(data) > 8 * 1024 * 1024:
            self.ks_client.upload_file_chunked(endpoint, upload_token, data, account_id=account_id, idempotency_key=idempotency_key)
        else:
            self.ks_client.upload_file(endpoint, upload_token, data, filename, account_id=account_id, idempotency_key=idempotency_key)
        return {"id": upload_token, "upload_token": upload_token, "endpoint": endpoint}

    def publish(self, job) -> dict[str, Any]:
        account = self.get_account(job.account_id)
        creds = self._credentials(account)
        token = str(creds.get("access_token") or "")
        uploaded = list((job.variant.metadata or {}).get("uploaded_media") or [])
        upload_token = ""
        if uploaded:
            upload_token = str(uploaded[0].get("remote_id") or uploaded[0].get("upload_token") or "")
        if not upload_token:
            raise ValidationError("Kuaishou publish requires upload_token from start_upload")
        payload = {
            "upload_token": upload_token,
            "caption": job.variant.caption or job.variant.body or job.variant.title,
        }
        cover = (job.variant.metadata or {}).get("cover")
        if cover:
            payload["cover"] = cover
        if (job.variant.metadata or {}).get("stereo_type"):
            payload["stereo_type"] = (job.variant.metadata or {}).get("stereo_type")
        result = self.ks_client.publish(
            self.app_id,
            token,
            payload,
            request_id=job.request_id,
            distribution_job_id=job.job_id,
            account_id=job.account_id,
            idempotency_key=job.idempotency_key or job.job_id,
        )
        photo = photo_from_payload(result if isinstance(result, dict) else {})
        if not photo.photo_id:
            raise PublishError("Kuaishou publish did not return photo_id; success is not PUBLISHED")
        return {
            "id": photo.photo_id,
            "post_id": photo.photo_id,
            "external_id": photo.photo_id,
            "status": map_status(photo),
            "provider_object_type": "photo",
        }

    def get_status(self, provider_post_id: str) -> dict[str, Any]:
        creds = self._credentials()
        token = str(creds.get("access_token") or "")
        if not token:
            raise AuthenticationError("Kuaishou status is BLOCKED: access token missing")
        result = self.ks_client.photo_info(self.app_id, token, provider_post_id)
        photo = photo_from_payload(result if isinstance(result, dict) else {})
        return {"id": photo.photo_id or provider_post_id, "status": map_status(photo), "raw": result, "provider_object_type": "photo"}

    def analytics(self, publication) -> dict[str, Any | None]:
        try:
            raw = self.get_status(publication.provider_post_id)
        except Exception:
            return {"views": None, "likes": None, "comments": None, "shares": None, "followers_delta": None}
        photo = photo_from_payload(raw.get("raw") if isinstance(raw.get("raw"), dict) else raw)
        return {
            "views": photo.view_count,
            "likes": photo.like_count,
            "comments": photo.comment_count,
            "shares": None,
            "followers_delta": None,
        }
