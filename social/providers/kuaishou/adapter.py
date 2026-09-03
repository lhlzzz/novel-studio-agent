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
        from datetime import datetime, timezone
        from social.providers.kuaishou.contract import PHOTO_INFO, PUBLISH, START_UPLOAD, USER_INFO

        account = self.get_account(account_id)
        creds = self._credentials(account)
        token = str(creds.get("access_token") or "")
        now = datetime.now(timezone.utc).isoformat()
        if not token:
            return SocialProviderCapabilities.from_claimed(CLAIMED, verified=False, method="unverified")
        try:
            payload = self.ks_client.user_info(self.app_id, token)
            user = user_from_payload(payload if isinstance(payload, dict) else {})
            if not user.user_id:
                raise AuthenticationError("user_id missing")
            user_ok = True
        except Exception:
            return SocialProviderCapabilities.from_claimed(CLAIMED, verified=False, method="unverified")
        record = self.secrets.get_record(account.credential_ref) if account.credential_ref else None
        scopes = (record.scopes or record.scope or "") if record is not None else ""
        scope_set = {item.strip() for item in scopes.replace(",", " ").split() if item.strip()}
        scope_ok = all(name in scope_set for name in REQUIRED_SCOPES) if scope_set else False
        records = {name: CapabilityRecord(name=name, supported=bool(value), verified=False, method="unverified") for name, value in CLAIMED.items()}
        records["user_info"] = CapabilityRecord(name="user_info", supported=True, verified=user_ok, verified_at=now, method="official_endpoint_probe", evidence={"endpoint": USER_INFO})
        from integrations.contracts.distribution import make_capability
        records["publish"] = make_capability("publish", supported=True, authorized=scope_ok, contract_verified=True, live_verified=False, method="official_scope" if scope_ok else "scope_missing", evidence={"scope": "user_video_publish", "endpoint": PUBLISH}, verified_at=now if scope_ok else None)
        records["video"] = make_capability("video", supported=True, authorized=scope_ok, contract_verified=True, live_verified=False, method="official_scope" if scope_ok else "scope_missing", evidence={"scope": "user_video_publish", "endpoint": PUBLISH})
        records["media_upload"] = make_capability("media_upload", supported=True, authorized=scope_ok, contract_verified=True, live_verified=False, method="official_scope" if scope_ok else "scope_missing", evidence={"scope": "user_video_publish", "endpoint": START_UPLOAD})
        records["analytics"] = make_capability("analytics", supported=True, authorized=scope_ok, contract_verified=True, live_verified=False, method="official_scope" if scope_ok else "scope_missing", evidence={"scope": "user_video_publish", "endpoint": PHOTO_INFO})
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
        if not endpoint.startswith("https://"):
            raise MediaUploadError("Kuaishou upload endpoint must be the HTTPS runtime value from start_upload")
        from social.providers.kuaishou.contract import WHOLE_FILE_LIMIT
        if len(data) > WHOLE_FILE_LIMIT:
            self.ks_client.upload_file_chunked(endpoint, upload_token, data, account_id=account_id, idempotency_key=idempotency_key)
        else:
            self.ks_client.upload_file(endpoint, upload_token, data, filename, account_id=account_id, idempotency_key=idempotency_key)
        return {"id": upload_token, "upload_token": upload_token, "endpoint": endpoint}

    def publish(self, job) -> dict[str, Any]:
        account = self.get_account(job.account_id)
        creds = self._credentials(account)
        token = str(creds.get("access_token") or "")
        from social.providers.base import job_uploaded_media
        uploaded = job_uploaded_media(job)
        upload_token = ""
        if uploaded:
            upload_token = str(uploaded[0].remote_id or uploaded[0].provider_media_id or uploaded[0].remote_path)
        if not upload_token:
            raise ValidationError("Kuaishou publish requires upload_token from start_upload")
        payload = {
            "upload_token": upload_token,
            "caption": job.variant.caption or job.variant.body or job.variant.title,
        }
        cover = (job.variant.metadata or {}).get("cover")
        cover_file = None
        if cover:
            from pathlib import Path
            path = Path(str(cover))
            if path.exists() and path.is_file():
                cover_file = (path.name, path.read_bytes(), "image/jpeg")
            elif str(cover).startswith(("http://", "https://")):
                payload["cover"] = cover
            else:
                raise ValidationError("Kuaishou cover must be an uploaded remote URL or a local file to send as multipart; JSON local paths are blocked")
        if (job.variant.metadata or {}).get("stereo_type"):
            payload["stereo_type"] = (job.variant.metadata or {}).get("stereo_type")
        result = self.ks_client.publish(
            self.app_id,
            token,
            payload,
            cover_file=cover_file,
            request_id=job.request_id,
            distribution_job_id=job.job_id,
            account_id=job.account_id,
            idempotency_key=job.idempotency_key or job.job_id,
        )
        photo = photo_from_payload(result if isinstance(result, dict) else {})
        if not photo.photo_id:
            raise PublishError("Kuaishou publish did not return photo_id; success is not PUBLISHED")
        extra = result if isinstance(result, dict) else {}
        request_id = str(extra.get("provider_request_id") or extra.get("request_id") or "") or None
        return {
            "provider_object_id": photo.photo_id,
            "post_id": photo.photo_id,
            "external_id": photo.photo_id,
            "status": "processing",
            "provider_object_type": "photo",
            "provider_request_id": request_id,
        }

    def get_status(self, provider_post_id: str, *, provider_object_type: str = "") -> dict[str, Any]:
        account = next(iter(self._accounts.values()), None)
        creds = self._credentials(account)
        token = str(creds.get("access_token") or "")
        if not token:
            raise AuthenticationError("Kuaishou status is BLOCKED: access token missing")
        result = self.ks_client.photo_info(self.app_id, token, provider_post_id)
        photo = photo_from_payload(result if isinstance(result, dict) else {})
        return {"id": photo.photo_id or provider_post_id, "status": map_status(photo), "raw": result, "provider_object_type": "photo"}

    def analytics(self, publication) -> dict[str, Any | None]:
        from social.providers.kuaishou.analytics import KuaishouAnalyticsClient
        creds = self._credentials(self.get_account(publication.account_id) if publication.account_id else None)
        token = str(creds.get("access_token") or "")
        return KuaishouAnalyticsClient(self.ks_client, self.app_id).fetch(token, publication.provider_post_id)
