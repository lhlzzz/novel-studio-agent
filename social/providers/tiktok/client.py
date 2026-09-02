"""Official tiktok HTTP owner.

OAuth: https://www.tiktok.com/v2/auth/authorize/
Token: https://open.tiktokapis.com/v2/oauth/token/
User: GET /user/info/
Publish init: POST /post/publish/inbox/video/init/
"""

from __future__ import annotations

from social.providers.http import SocialHttpClient

class TikTokClient:
    def __init__(self, *, http: SocialHttpClient | None = None) -> None:
        self.http = http or SocialHttpClient(provider="tiktok", base_url="https://open.tiktokapis.com/v2")
