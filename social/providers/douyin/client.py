from __future__ import annotations

from typing import Any

from social.providers.douyin.contract import (
    API_BASE,
    COMPLETE_PART,
    CREATE_IMAGE_TEXT,
    CREATE_VIDEO,
    INIT_PART,
    UPLOAD_PART,
    UPLOAD_IMAGE,
    UPLOAD_VIDEO,
    VIDEO_DATA,
)
from social.providers.errors import AuthenticationError, MediaUploadError, ProviderError, PublishError
from social.providers.http import SocialHttpClient


def unwrap_douyin(payload: Any, *, kind: str = "request") -> Any:
    if not isinstance(payload, dict):
        return payload
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    code = extra.get("error_code")
    if code in (None, "", 0, "0"):
        code = data.get("error_code") if isinstance(data, dict) else None
    if code not in (None, "", 0, "0"):
        message = str(
            extra.get("description")
            or data.get("description")
            or extra.get("sub_description")
            or payload
        )
        logid = str(extra.get("logid") or extra.get("log_id") or "")
        cls = ProviderError
        if kind in {"upload", "upload_image", "upload_video"}:
            cls = MediaUploadError
        elif kind in {"publish", "create_video", "create_image_text"}:
            cls = PublishError
        elif kind in {"oauth", "token", "refresh", "userinfo"}:
            cls = AuthenticationError
        raise cls(f"Douyin {kind} failed: {message}", provider_error_code=str(code), request_id=logid or None)
    logid = extra.get("logid") or extra.get("log_id")
    if logid and not payload.get("provider_request_id"):
        payload = dict(payload)
        payload["provider_request_id"] = str(logid)
    return payload


class DouyinClient:
    def __init__(self, *, http: SocialHttpClient | None = None) -> None:
        self.http = http or SocialHttpClient(provider="douyin", base_url=API_BASE)

    def _headers(self, access_token: str) -> dict[str, str]:
        return {"access-token": access_token, "Authorization": f"Bearer {access_token}"}

    def upload_video(self, access_token: str, open_id: str, data: bytes, *, filename: str = "video.mp4", mime_type: str = "video/mp4", **ctx: str) -> Any:
        return unwrap_douyin(
            self.http.request(
                "POST",
                UPLOAD_VIDEO,
                headers=self._headers(access_token),
                query={"open_id": open_id},
                files={"video": (filename, data, mime_type)},
                **ctx,
            ),
            kind="upload_video",
        )

    def upload_image(self, access_token: str, open_id: str, data: bytes, *, filename: str = "image.jpg", mime_type: str = "image/jpeg", **ctx: str) -> Any:
        return unwrap_douyin(
            self.http.request(
                "POST",
                UPLOAD_IMAGE,
                headers=self._headers(access_token),
                query={"open_id": open_id},
                files={"image": (filename, data, mime_type)},
                **ctx,
            ),
            kind="upload_image",
        )

    def init_part(self, access_token: str, open_id: str, **ctx: str) -> Any:
        return unwrap_douyin(
            self.http.request("POST", INIT_PART, headers=self._headers(access_token), query={"open_id": open_id}, json_body={}, **ctx),
            kind="upload",
        )

    def upload_part(self, access_token: str, open_id: str, upload_id: str, part_number: int, data: bytes, **ctx: str) -> Any:
        return unwrap_douyin(
            self.http.request(
                "POST",
                UPLOAD_PART,
                headers=self._headers(access_token),
                query={"open_id": open_id, "upload_id": upload_id, "part_number": part_number},
                files={"video": ("part.mp4", data, "application/octet-stream")},
                **ctx,
            ),
            kind="upload",
        )

    def complete_part(self, access_token: str, open_id: str, upload_id: str, **ctx: str) -> Any:
        return unwrap_douyin(
            self.http.request(
                "POST",
                COMPLETE_PART,
                headers=self._headers(access_token),
                query={"open_id": open_id},
                json_body={"upload_id": upload_id},
                **ctx,
            ),
            kind="upload",
        )

    def create_video(self, access_token: str, open_id: str, payload: dict[str, Any], **ctx: str) -> Any:
        return unwrap_douyin(
            self.http.request(
                "POST",
                CREATE_VIDEO,
                headers=self._headers(access_token),
                query={"open_id": open_id},
                json_body=payload,
                **ctx,
            ),
            kind="create_video",
        )

    def create_image_text(self, access_token: str, open_id: str, payload: dict[str, Any], **ctx: str) -> Any:
        return unwrap_douyin(
            self.http.request(
                "POST",
                CREATE_IMAGE_TEXT,
                headers=self._headers(access_token),
                query={"open_id": open_id},
                json_body=payload,
                **ctx,
            ),
            kind="create_image_text",
        )

    def video_data(self, access_token: str, open_id: str, item_ids: list[str], **ctx: str) -> Any:
        return unwrap_douyin(
            self.http.request(
                "POST",
                VIDEO_DATA,
                headers=self._headers(access_token),
                query={"open_id": open_id},
                json_body={"item_ids": item_ids},
                **ctx,
            ),
            kind="video_data",
        )
