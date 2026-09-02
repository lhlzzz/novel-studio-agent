"""Official instagram HTTP owner.

OAuth: https://www.facebook.com/v21.0/dialog/oauth
Token: https://graph.facebook.com/v21.0/oauth/access_token
Create container: POST /{ig-user-id}/media
Publish: POST /{ig-user-id}/media_publish
Me: GET /me/accounts
"""

from __future__ import annotations

from social.providers.http import SocialHttpClient

class InstagramClient:
    def __init__(self, *, http: SocialHttpClient | None = None) -> None:
        self.http = http or SocialHttpClient(provider="instagram", base_url="https://graph.facebook.com/v21.0")
