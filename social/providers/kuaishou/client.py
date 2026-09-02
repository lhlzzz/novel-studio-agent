from __future__ import annotations

from typing import Any

from social.providers.http import SocialHttpClient
from social.providers.kuaishou.contract import API_BASE, PHOTO_INFO, PUBLISH, START_UPLOAD, USER_INFO


class KuaishouClient:
    def __init__(self, *, http: SocialHttpClient | None = None) -> None:
        self.http = http or SocialHttpClient(provider="kuaishou", base_url=API_BASE)

    def user_info(self, app_id: str, access_token: str, **ctx: str) -> Any:
        return self.http.request("GET", USER_INFO, query={"app_id": app_id, "access_token": access_token}, **ctx)

    def start_upload(self, app_id: str, access_token: str, **ctx: str) -> Any:
        return self.http.request("POST", START_UPLOAD, query={"app_id": app_id, "access_token": access_token}, **ctx)

    def upload_file(self, endpoint: str, upload_token: str, data: bytes, filename: str, **ctx: str) -> Any:
        url = endpoint.rstrip("/")
        if not url.startswith("http"):
            raise ValueError("Kuaishou upload endpoint must come from start_upload")
        return self.http.request(
            "POST",
            f"{url}/api/upload",
            query={"upload_token": upload_token},
            data=data,
            content_type="application/octet-stream",
            extra_headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            absolute=True,
            **ctx,
        )

    def upload_file_chunked(self, endpoint: str, upload_token: str, data: bytes, *, chunk_size: int = 4 * 1024 * 1024, **ctx: str) -> Any:
        url = endpoint.rstrip("/")
        last = None
        fragment = 0
        for offset in range(0, len(data), chunk_size):
            chunk = data[offset: offset + chunk_size]
            last = self.http.request(
                "POST",
                f"{url}/api/upload/fragment",
                query={"upload_token": upload_token, "fragment_id": fragment},
                data=chunk,
                content_type="application/octet-stream",
                absolute=True,
                **ctx,
            )
            fragment += 1
        complete = self.http.request(
            "POST",
            f"{url}/api/upload/complete",
            query={"upload_token": upload_token, "fragment_count": fragment},
            absolute=True,
            **ctx,
        )
        return complete or last

    def publish(self, app_id: str, access_token: str, payload: dict[str, Any], *, cover_file=None, **ctx: str) -> Any:
        files = {}
        if cover_file is not None:
            files["cover"] = cover_file
        return self.http.request(
            "POST",
            PUBLISH,
            query={"app_id": app_id, "access_token": access_token},
            json_body=payload,
            files=files,
            multipart=True,
            **ctx,
        )

    def photo_info(self, app_id: str, access_token: str, photo_id: str, **ctx: str) -> Any:
        return self.http.request("GET", PHOTO_INFO, query={"app_id": app_id, "access_token": access_token, "photo_id": photo_id}, **ctx)
