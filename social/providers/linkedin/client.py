"""Official linkedin HTTP owner.

OAuth: https://www.linkedin.com/oauth/v2/authorization
Token: https://www.linkedin.com/oauth/v2/accessToken
User: GET https://api.linkedin.com/v2/userinfo
Posts: POST /posts
Image upload: POST /images?action=initializeUpload
"""

from __future__ import annotations

from social.providers.http import SocialHttpClient

class LinkedInClient:
    def __init__(self, *, http: SocialHttpClient | None = None) -> None:
        self.http = http or SocialHttpClient(provider="linkedin", base_url="https://api.linkedin.com/rest")
