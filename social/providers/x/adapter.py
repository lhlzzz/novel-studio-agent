"""Native X adapter. Official API only; missing credentials stay BLOCKED."""

from __future__ import annotations

from typing import Any

from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.providers.base import NULL_ANALYTICS, BaseSocialAdapter
from social.providers.errors import AuthenticationError, ValidationError
from social.providers.x.auth import XAuth
from social.providers.x.capabilities import CLAIMED
from social.providers.x.client import XClient
from social.providers.x.schemas import tweet_from_payload, user_from_payload


class XAdapter(BaseSocialAdapter):
    provider = "x"
    platform = "x"
    api_base = "https://api.x.com/2"
    claimed = CLAIMED

    def __init__(self, *, client: XClient | None = None, secrets: Any | None = None) -> None:
        http = None if client is None else client.http
        super().__init__(client=http, secrets=secrets)
        self.x_client = client or XClient(http=self.client)
        self.auth = XAuth(client=self.client)

    def authenticate(self, authorization: dict[str, Any] | None = None) -> bool:
        authorization = authorization or {}
        if authorization.get("access_token"):
            ref = self.secrets.put({"access_token": authorization["access_token"], "refresh_token": authorization.get("refresh_token")})
            self._credential_ref = ref
            return True
        if authorization.get("code") and authorization.get("code_verifier"):
            tokens = self.auth.exchange_code(str(authorization["code"]), code_verifier=str(authorization["code_verifier"]))
            ref = self.secrets.put(tokens)
            self._credential_ref = ref
            return True
        return super().authenticate(authorization)

    def _discover_accounts(self, creds: dict[str, Any]) -> list[SocialAccount]:
        headers = self._auth_headers()
        if not headers:
            raise AuthenticationError("X account discovery is BLOCKED: access token missing")
        payload = self.x_client.users_me(headers)
        user = user_from_payload(payload if isinstance(payload, dict) else {})
        if not user.id:
            raise AuthenticationError("X /2/users/me did not return a user id")
        account = SocialAccount(
            account_id=f"x:{user.id}",
            provider="x",
            platform="x",
            username=user.username,
            display_name=user.name,
            avatar_url=user.profile_image_url,
            status="AUTHENTICATED",
            capabilities=SocialProviderCapabilities.from_claimed(CLAIMED),
            provider_account_id=user.id,
            credential_ref=getattr(self, "_credential_ref", ""),
        )
        return [account]

    def _validate_platform(self, job, account) -> list[str]:
        errors: list[str] = []
        if not job.variant.body.strip() and not job.variant.media:
            errors.append("X requires text or media")
        if job.variant.body and len(job.variant.body) > 280 and not account.capabilities.verified("thread"):
            errors.append("X text exceeds 280 characters")
        return errors

    def _upload_bytes(self, data: bytes, *, mime_type: str, filename: str, account_id: str, idempotency_key: str) -> dict[str, Any]:
        headers = self._auth_headers()
        if not headers:
            raise AuthenticationError("X media upload is BLOCKED: access token missing")
        media_type = "tweet_video" if mime_type.startswith("video/") else "tweet_image"
        initialized = self.x_client.initialize_media(
            headers,
            {"media_category": media_type, "media_type": mime_type, "total_bytes": len(data)},
            account_id=account_id,
            idempotency_key=idempotency_key,
        )
        media_id = str((initialized.get("data") or initialized).get("id") or (initialized.get("data") or {}).get("media_id") or "")
        if not media_id:
            raise ValidationError("X media initialize did not return media id")
        self.x_client.append_media(headers, media_id, data, account_id=account_id, idempotency_key=idempotency_key)
        finalized = self.x_client.finalize_media(headers, media_id, account_id=account_id, idempotency_key=idempotency_key)
        final_id = str((finalized.get("data") or finalized).get("id") or media_id)
        return {"id": final_id}

    def publish(self, job) -> dict[str, Any]:
        headers = self._auth_headers(self.get_account(job.account_id) if job.account_id in {item.account_id for item in self.list_accounts()} else None)
        if not headers:
            headers = self._auth_headers()
        if not headers:
            raise AuthenticationError("X publish is BLOCKED: access token missing")
        payload: dict[str, Any] = {}
        if job.variant.body.strip():
            payload["text"] = job.variant.body
        media_ids = [
            str(item.get("remote_id"))
            for item in (job.variant.metadata or {}).get("uploaded_media") or []
            if item.get("remote_id")
        ]
        if media_ids:
            payload["media"] = {"media_ids": media_ids}
        result = self.x_client.create_tweet(
            headers,
            payload,
            request_id=job.request_id,
            distribution_job_id=job.job_id,
            account_id=job.account_id,
            idempotency_key=job.idempotency_key or job.job_id,
        )
        tweet = tweet_from_payload(result if isinstance(result, dict) else {})
        if not tweet.id:
            raise ValidationError("X create tweet did not return an id")
        return {
            "id": tweet.id,
            "post_id": tweet.id,
            "external_id": tweet.id,
            "status": "published",
            "url": f"https://x.com/i/web/status/{tweet.id}",
        }

    def get_status(self, provider_post_id: str, *, provider_object_type: str = "") -> dict[str, Any]:
        headers = self._auth_headers()
        if not headers:
            raise AuthenticationError("X status is BLOCKED: access token missing")
        result = self.x_client.get_tweet(headers, provider_post_id)
        tweet = tweet_from_payload(result if isinstance(result, dict) else {})
        return {"id": tweet.id or provider_post_id, "status": "published" if tweet.id else "UNKNOWN", "raw": result}

    def delete(self, provider_post_id: str) -> dict[str, Any]:
        headers = self._auth_headers()
        if not headers:
            raise AuthenticationError("X delete is BLOCKED: access token missing")
        return self.x_client.delete_tweet(headers, provider_post_id)

    def analytics(self, publication) -> dict[str, Any | None]:
        headers = self._auth_headers()
        if not headers:
            return dict(NULL_ANALYTICS)
        result = self.x_client.get_tweet(headers, publication.provider_post_id)
        tweet = tweet_from_payload(result if isinstance(result, dict) else {})
        metrics = tweet.public_metrics or {}
        return {
            "views": metrics.get("impression_count"),
            "likes": metrics.get("like_count"),
            "comments": metrics.get("reply_count"),
            "shares": metrics.get("retweet_count"),
            "followers_delta": None,
        }
