from __future__ import annotations

from typing import Any

from social.providers.douyin.contract import (
    API_BASE,
    COMPLETE_PART,
    CREATE_IMAGE_TEXT,
    CREATE_VIDEO,
    INIT_PART,
    UPLOAD_PART,
    UPLOAD_VIDEO,
    VIDEO_DATA,
)
from social.providers.http import SocialHttpClient


class DouyinClient:
    def __init__(self, *, http: SocialHttpClient | None = None) -> None:
        self.http = http or SocialHttpClient(provider="douyin", base_url=API_BASE)

    def _headers(self, access_token: str) -> dict[str, str]:
        return {"access-token": access_token, "Authorization": f"Bearer {access_token}"}

    def upload_video(self, access_token: str, open_id: str, data: bytes, **ctx: str) -> Any:
        return self.http.request(
            "POST",
            UPLOAD_VIDEO,
            headers=self._headers(access_token),
            query={"open_id": open_id},
            data=data,
            content_type="application/octet-stream",
            **ctx,
        )

    def init_part(self, access_token: str, open_id: str, **ctx: str) -> Any:
        return self.http.request("POST", INIT_PART, headers=self._headers(access_token), query={"open_id": open_id}, json_body={}, **ctx)

    def upload_part(self, access_token: str, open_id: str, upload_id: str, part_number: int, data: bytes, **ctx: str) -> Any:
        return self.http.request(
            "POST",
            UPLOAD_PART,
            headers=self._headers(access_token),
            query={"open_id": open_id, "upload_id": upload_id, "part_number": part_number},
            data=data,
            content_type="application/octet-stream",
            **ctx,
        )

    def complete_part(self, access_token: str, open_id: str, upload_id: str, **ctx: str) -> Any:
        return self.http.request(
            "POST",
            COMPLETE_PART,
            headers=self._headers(access_token),
            query={"open_id": open_id},
            json_body={"upload_id": upload_id},
            **ctx,
        )

    def create_video(self, access_token: str, open_id: str, payload: dict[str, Any], **ctx: str) -> Any:
        return self.http.request(
            "POST",
            CREATE_VIDEO,
            headers=self._headers(access_token),
            query={"open_id": open_id},
            json_body=payload,
            **ctx,
        )

    def create_image_text(self, access_token: str, open_id: str, payload: dict[str, Any], **ctx: str) -> Any:
        return self.http.request(
            "POST",
            CREATE_IMAGE_TEXT,
            headers=self._headers(access_token),
            query={"open_id": open_id},
            json_body=payload,
            **ctx,
        )

    def video_data(self, access_token: str, open_id: str, item_ids: list[str], **ctx: str) -> Any:
        return self.http.request(
            "POST",
            VIDEO_DATA,
            headers=self._headers(access_token),
            query={"open_id": open_id},
            json_body={"item_ids": item_ids},
            **ctx,
        )
