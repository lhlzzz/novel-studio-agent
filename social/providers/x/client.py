"""Single HTTP owner for official X API v2 endpoints."""

from __future__ import annotations

from typing import Any

from social.providers.http import SocialHttpClient

API_BASE = "https://api.x.com/2"
MEDIA_INITIALIZE = "/media/upload/initialize"
MEDIA_APPEND = "/media/upload/{id}/append"
MEDIA_FINALIZE = "/media/upload/{id}/finalize"


class XClient:
    def __init__(self, *, http: SocialHttpClient | None = None) -> None:
        self.http = http or SocialHttpClient(provider="x", base_url=API_BASE)

    def users_me(self, headers: dict[str, str], **ctx: str) -> Any:
        return self.http.request(
            "GET",
            "/users/me",
            headers=headers,
            query={"user.fields": "id,name,username,profile_image_url"},
            **ctx,
        )

    def create_tweet(self, headers: dict[str, str], payload: dict[str, Any], **ctx: str) -> Any:
        return self.http.request("POST", "/tweets", headers=headers, json_body=payload, **ctx)

    def get_tweet(self, headers: dict[str, str], tweet_id: str, **ctx: str) -> Any:
        return self.http.request(
            "GET",
            f"/tweets/{tweet_id}",
            headers=headers,
            query={"tweet.fields": "id,text,created_at,public_metrics"},
            **ctx,
        )

    def delete_tweet(self, headers: dict[str, str], tweet_id: str, **ctx: str) -> Any:
        return self.http.request("DELETE", f"/tweets/{tweet_id}", headers=headers, **ctx)

    def initialize_media(self, headers: dict[str, str], payload: dict[str, Any], **ctx: str) -> Any:
        return self.http.request("POST", MEDIA_INITIALIZE, headers=headers, json_body=payload, **ctx)

    def append_media(self, headers: dict[str, str], media_id: str, data: bytes, **ctx: str) -> Any:
        return self.http.request(
            "POST",
            MEDIA_APPEND.format(id=media_id),
            headers=headers,
            data=data,
            content_type="application/octet-stream",
            **ctx,
        )

    def finalize_media(self, headers: dict[str, str], media_id: str, **ctx: str) -> Any:
        return self.http.request("POST", MEDIA_FINALIZE.format(id=media_id), headers=headers, json_body={"id": media_id}, **ctx)
