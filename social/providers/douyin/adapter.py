from __future__ import annotations

from typing import Any

from integrations.contracts.distribution import CapabilityRecord
from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.auth.credentials import CredentialRecord
from social.providers.base import BaseCNAdapter
from social.providers.douyin.auth import DouyinAuth
from social.providers.douyin.capabilities import CLAIMED, REQUIRED_PUBLISH_SCOPES
from social.providers.douyin.client import DouyinClient
from social.providers.douyin.contract import PART_SIZE, SMALL_UPLOAD_LIMIT
from social.providers.douyin.schemas import map_status, user_from_payload, video_from_payload
from social.providers.errors import AuthenticationError, MediaUploadError, PublishError, ValidationError
from social.media_policy import validate_job


class DouyinAdapter(BaseCNAdapter):
    provider = "douyin"
    platform = "douyin"
    api_base = "https://open.douyin.com"
    claimed = CLAIMED

    def __init__(self, *, client: DouyinClient | None = None, secrets: Any | None = None) -> None:
        http = None if client is None else client.http
        super().__init__(client=http, secrets=secrets)
        self.dy_client = client or DouyinClient(http=self.client)
        self.auth = DouyinAuth(client=self.client)

    def authenticate(self, authorization: dict[str, Any] | None = None) -> bool:
        authorization = authorization or {}
        if authorization.get("code"):
            record = self.auth.exchange_code(str(authorization["code"]))
            ref = self.secrets.put(record)
            self._credential_ref = ref
            return True
        if authorization.get("access_token"):
            record = CredentialRecord.from_payload({**authorization, "provider": "douyin"})
            self._credential_ref = self.secrets.put(record)
            return True
        return super().authenticate(authorization)

    def _token(self, account: SocialAccount | None = None) -> tuple[str, str]:
        creds = self._credentials(account)
        token = str(creds.get("access_token") or "")
        open_id = str(creds.get("open_id") or creds.get("provider_account_id") or (account.provider_account_id if account else "") or "")
        if not token:
            raise AuthenticationError("Douyin access_token missing")
        return token, open_id

    def _discover_accounts(self, creds: dict[str, Any]) -> list[SocialAccount]:
        token = str(creds.get("access_token") or "")
        if not token:
            raise AuthenticationError("Douyin account discovery is BLOCKED: access token missing")
        payload = self.auth.validate(token)
        user = user_from_payload(payload if isinstance(payload, dict) else {})
        if not user.open_id:
            data = creds.get("open_id")
            if not data:
                raise AuthenticationError("Douyin userinfo did not return open_id")
            user = user_from_payload({"open_id": data, "nickname": creds.get("nickname") or ""})
        account = SocialAccount(
            account_id=f"douyin:{user.open_id}",
            provider="douyin",
            platform="douyin",
            username=user.nickname,
            display_name=user.nickname,
            avatar_url=user.avatar,
            status="AUTHENTICATED",
            region="cn",
            capabilities=SocialProviderCapabilities.from_claimed(CLAIMED),
            provider_account_id=user.open_id,
            credential_ref=getattr(self, "_credential_ref", "") or "",
        )
        return [account]

    def verify_capabilities(self, account_id: str) -> SocialProviderCapabilities:
        account = self.get_account(account_id)
        try:
            token, open_id = self._token(account)
            payload = self.auth.validate(token)
            user = user_from_payload(payload if isinstance(payload, dict) else {})
            if not (user.open_id or open_id):
                raise AuthenticationError("open_id missing")
        except Exception:
            return SocialProviderCapabilities.from_claimed(CLAIMED, verified=False, method="unverified")
        record = self.secrets.get_record(account.credential_ref) if account.credential_ref else None
        scopes = (record.scopes or record.scope or "") if record is not None else ""
        publish_ok = all(account_scope in scopes.replace(",", " ").split() for account_scope in REQUIRED_PUBLISH_SCOPES) if scopes else False
        method = "runtime_probe"
        records = {
            name: CapabilityRecord(name=name, supported=bool(value), verified=bool(value and (name != "publish" or publish_ok or name in {"media_upload", "image", "video", "analytics"})), method=method, verification_method=method)
            for name, value in CLAIMED.items()
        }
        if not publish_ok:
            records["publish"] = CapabilityRecord(name="publish", supported=True, verified=False, method="scope_missing")
        else:
            records["publish"] = CapabilityRecord(name="publish", supported=True, verified=True, method=method)
        return SocialProviderCapabilities.from_records(records)

    def _validate_platform(self, job, account) -> list[str]:
        return validate_job(job, platform="douyin")

    def _upload_bytes(self, data: bytes, *, mime_type: str, filename: str, account_id: str, idempotency_key: str) -> dict[str, Any]:
        account = self.get_account(account_id) if account_id else None
        token, open_id = self._token(account)
        if mime_type.startswith("image/"):
            result = self.dy_client.upload_video(token, open_id, data, account_id=account_id, idempotency_key=idempotency_key)
            image_id = str(((result.get("data") or result) if isinstance(result, dict) else {}).get("image_id") or ((result.get("data") or {}) if isinstance(result, dict) else {}).get("id") or "")
            if not image_id:
                raise MediaUploadError("Douyin image upload did not return image_id")
            return {"id": image_id}
        if len(data) <= SMALL_UPLOAD_LIMIT:
            result = self.dy_client.upload_video(token, open_id, data, account_id=account_id, idempotency_key=idempotency_key)
        else:
            initialized = self.dy_client.init_part(token, open_id, account_id=account_id, idempotency_key=idempotency_key)
            upload_id = str(((initialized.get("data") or initialized) if isinstance(initialized, dict) else {}).get("upload_id") or "")
            if not upload_id:
                raise MediaUploadError("Douyin init_video_part_upload did not return upload_id")
            part = 1
            for offset in range(0, len(data), PART_SIZE):
                chunk = data[offset: offset + PART_SIZE]
                self.dy_client.upload_part(token, open_id, upload_id, part, chunk, account_id=account_id, idempotency_key=idempotency_key)
                part += 1
            result = self.dy_client.complete_part(token, open_id, upload_id, account_id=account_id, idempotency_key=idempotency_key)
        video_id = str(((result.get("data") or result) if isinstance(result, dict) else {}).get("video_id") or "")
        if not video_id:
            raise MediaUploadError("Douyin video upload did not return video_id")
        return {"id": video_id}

    def publish(self, job) -> dict[str, Any]:
        account = self.get_account(job.account_id)
        token, open_id = self._token(account)
        uploaded = list((job.variant.metadata or {}).get("uploaded_media") or [])
        media_ids = [str(item.get("remote_id")) for item in uploaded if item.get("remote_id")]
        videos = [path for path in job.variant.media if str(path).lower().endswith((".mp4", ".mov"))]
        if videos:
            if not media_ids:
                raise ValidationError("Douyin video publish requires uploaded video_id")
            payload = {"video_id": media_ids[0], "text": job.variant.body or job.variant.caption or job.variant.title}
            result = self.dy_client.create_video(token, open_id, payload, request_id=job.request_id, distribution_job_id=job.job_id, account_id=job.account_id, idempotency_key=job.idempotency_key or job.job_id)
            object_type = "video"
        else:
            payload = {"image_list": [{"image_id": item} for item in media_ids], "text": job.variant.body or job.variant.caption or job.variant.title}
            result = self.dy_client.create_image_text(token, open_id, payload, request_id=job.request_id, distribution_job_id=job.job_id, account_id=job.account_id, idempotency_key=job.idempotency_key or job.job_id)
            object_type = "video"
        video = video_from_payload(result if isinstance(result, dict) else {})
        item_id = video.item_id or video.video_id
        if not item_id:
            raise PublishError("Douyin create did not return item_id; HTTP 200 is not PUBLISHED")
        return {
            "id": item_id,
            "post_id": item_id,
            "external_id": video.video_id or item_id,
            "status": map_status(video.video_status) if video.video_status else "processing",
            "provider_object_type": object_type,
        }

    def get_status(self, provider_post_id: str) -> dict[str, Any]:
        creds = self._credentials()
        token = str(creds.get("access_token") or "")
        open_id = str(creds.get("open_id") or creds.get("provider_account_id") or "")
        if not token:
            raise AuthenticationError("Douyin status is BLOCKED: access token missing")
        result = self.dy_client.video_data(token, open_id, [provider_post_id])
        data = result.get("data") if isinstance(result, dict) else {}
        items = data.get("list") if isinstance(data, dict) else None
        item = (items or [data or result])[0] if isinstance(items, list) and items else (data or result)
        video = video_from_payload(item if isinstance(item, dict) else {})
        return {"id": video.item_id or provider_post_id, "status": map_status(video.video_status), "raw": result, "provider_object_type": "video"}

    def analytics(self, publication) -> dict[str, Any | None]:
        try:
            raw = self.get_status(publication.provider_post_id)
        except Exception:
            return {"views": None, "likes": None, "comments": None, "shares": None, "followers_delta": None}
        item = raw.get("raw") or {}
        data = item.get("data") if isinstance(item, dict) else {}
        stats = data.get("list", [{}])[0] if isinstance(data, dict) and isinstance(data.get("list"), list) and data.get("list") else data
        if not isinstance(stats, dict):
            stats = {}
        return {
            "views": stats.get("play_count") or stats.get("view_count"),
            "likes": stats.get("digg_count") or stats.get("like_count"),
            "comments": stats.get("comment_count"),
            "shares": stats.get("share_count"),
            "followers_delta": None,
        }
