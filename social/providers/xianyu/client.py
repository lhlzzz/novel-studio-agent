from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

from social.providers.http import SocialHttpClient
from social.providers.xianyu.contract import METHODS, ROUTER


class XianyuClient:
    def __init__(self, *, http: SocialHttpClient | None = None, app_key: str = "", app_secret: str = "") -> None:
        self.http = http or SocialHttpClient(provider="xianyu", base_url="https://eco.taobao.com")
        self.app_key = app_key or os.getenv("XIANYU_APP_KEY", "").strip()
        self.app_secret = app_secret or os.getenv("XIANYU_APP_SECRET", "").strip()

    def call(self, method: str, session: str, biz: dict[str, Any], **ctx: str) -> Any:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        params = {
            "method": method,
            "app_key": self.app_key,
            "timestamp": timestamp,
            "format": "json",
            "v": "2.0",
            "sign_method": "md5",
            "session": session,
        }
        for key, value in biz.items():
            if value is not None:
                params[key] = value if isinstance(value, str) else str(value)
        params["sign"] = self._sign(params)
        from urllib.parse import urlencode
        body = urlencode(params).encode("utf-8")
        return self.http.request("POST", ROUTER, headers={"Content-Type": "application/x-www-form-urlencoded"}, data=body, absolute=True, **ctx)

    def _sign(self, params: dict[str, str]) -> str:
        pieces = "".join(f"{key}{params[key]}" for key in sorted(params) if key != "sign")
        raw = f"{self.app_secret}{pieces}{self.app_secret}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()

    def user_info(self, session: str, **ctx: str) -> Any:
        return self.call(METHODS["user_info"], session, {}, **ctx)

    def media_upload(self, session: str, url: str, **ctx: str) -> Any:
        if not str(url).startswith("https://"):
            raise ValueError("Xianyu media.upload accepts hosted HTTPS URLs only")
        return self.call(METHODS["media_upload"], session, {"url": url}, **ctx)

    def item_publish(self, session: str, item: dict[str, Any], **ctx: str) -> Any:
        return self.call(METHODS["item_publish"], session, item, **ctx)

    def item_query(self, session: str, item_id: str, **ctx: str) -> Any:
        return self.call(METHODS["item_query"], session, {"item_id": item_id}, **ctx)

    def item_edit(self, session: str, item: dict[str, Any], **ctx: str) -> Any:
        return self.call(METHODS["item_edit"], session, item, **ctx)

    def item_downshelf(self, session: str, item_id: str, **ctx: str) -> Any:
        return self.call(METHODS["item_downshelf"], session, {"item_id": item_id}, **ctx)
