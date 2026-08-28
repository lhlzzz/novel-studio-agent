"""Single HTTP client owner for the Postiz Public API."""

from __future__ import annotations

import json
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class PostizClientError(RuntimeError):
    """Raised when Postiz cannot be reached or rejects a request."""


class PostizClient:
    """Own URL, authentication, serialization, and all Postiz HTTP calls."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        *,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("POSTIZ_API_URL") or "http://127.0.0.1:4007"
        ).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("POSTIZ_API_KEY", "")
        self.timeout = timeout

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            values = {key: value for key, value in query.items() if value is not None}
            if values:
                url = f"{url}?{urlencode(values)}"
        request_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            request_headers["Authorization"] = self.api_key
        request_headers.update(headers or {})
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=data, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            detail = getattr(exc, "reason", None) or str(exc)
            status = getattr(exc, "code", "network")
            raise PostizClientError(
                f"Postiz {method} {path} failed ({status}): {detail}"
            ) from exc
        return self._decode(raw, method, path)

    @staticmethod
    def _decode(raw: bytes, method: str, path: str) -> Any:
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise PostizClientError(
                f"Postiz {method} {path} returned invalid JSON"
            ) from exc

    def list_integrations(self, group: str | None = None) -> Any:
        return self._request("/public/v1/integrations", query={"group": group})

    def get_integration_settings(self, integration_id: str) -> Any:
        return self._request(f"/public/v1/integration-settings/{integration_id}")

    def create_post(self, payload: dict[str, Any]) -> Any:
        return self._request("/public/v1/posts", method="POST", payload=payload)

    def list_posts(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Any:
        return self._request(
            "/public/v1/posts",
            query={"startDate": start_date, "endDate": end_date},
        )

    def delete_post(self, post_id: str) -> Any:
        return self._request(f"/public/v1/posts/{post_id}", method="DELETE")

    def upload_media(self, file_path: str | Path) -> Any:
        path = Path(file_path)
        if not path.is_file():
            raise PostizClientError(f"media file does not exist: {path}")
        boundary = f"----meiti-{uuid.uuid4().hex}"
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        content = path.read_bytes()
        body = b"--" + boundary.encode() + b"\r\n"
        body += (
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        ).encode()
        body += f"Content-Type: {content_type}\r\n\r\n".encode()
        body += content + b"\r\n--" + boundary.encode() + b"--\r\n"
        return self._multipart_request(body, boundary)

    def _multipart_request(self, body: bytes, boundary: str) -> Any:
        headers = {
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        }
        if self.api_key:
            headers["Authorization"] = self.api_key
        request = Request(
            f"{self.base_url}/public/v1/upload",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=max(self.timeout, 60.0)) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            detail = getattr(exc, "reason", None) or str(exc)
            status = getattr(exc, "code", "network")
            raise PostizClientError(
                f"Postiz POST /public/v1/upload failed ({status}): {detail}"
            ) from exc
        return self._decode(raw, "POST", "/public/v1/upload")

    def get_post_analytics(self, post_id: str, days: int = 7) -> Any:
        return self._request(
            f"/public/v1/analytics/post/{post_id}", query={"date": days}
        )

    def get_integration_analytics(self, integration_id: str, days: int = 30) -> Any:
        return self._request(
            f"/public/v1/analytics/{integration_id}", query={"date": days}
        )

    def trigger_integration_tool(
        self,
        integration_id: str,
        method_name: str,
        data: dict[str, Any] | None = None,
    ) -> Any:
        return self._request(
            f"/public/v1/integration-trigger/{integration_id}",
            method="POST",
            payload={"methodName": method_name, "data": data or {}},
        )
