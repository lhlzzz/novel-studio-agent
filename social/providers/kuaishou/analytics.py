from __future__ import annotations

from typing import Any

from social.providers.kuaishou.schemas import photo_from_payload


class KuaishouAnalyticsClient:
    def __init__(self, client, app_id: str) -> None:
        self.client = client
        self.app_id = app_id

    def fetch(self, access_token: str, photo_id: str) -> dict[str, Any | None]:
        result = self.client.photo_info(self.app_id, access_token, photo_id)
        photo = photo_from_payload(result if isinstance(result, dict) else {})
        return {
            "views": photo.view_count,
            "likes": photo.like_count,
            "comments": photo.comment_count,
            "shares": None,
            "followers_delta": None,
        }
