"""Official youtube HTTP owner.

OAuth: https://accounts.google.com/o/oauth2/v2/auth
Token: https://oauth2.googleapis.com/token
Upload: POST https://www.googleapis.com/upload/youtube/v3/videos
Channels: GET /channels?part=snippet&mine=true
Thumbnails: POST /thumbnails/set
"""

from __future__ import annotations

from social.providers.http import SocialHttpClient

class YouTubeClient:
    def __init__(self, *, http: SocialHttpClient | None = None) -> None:
        self.http = http or SocialHttpClient(provider="youtube", base_url="https://www.googleapis.com/youtube/v3")
