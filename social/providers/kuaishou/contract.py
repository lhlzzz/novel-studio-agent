"""Kuaishou Open Platform official video publish contract.

start_upload -> runtime HTTPS endpoint -> upload -> multipart publish -> photo_id -> photo_info
"""

CONTRACT_VERSION = "2026-09-03"
CONTRACT_SOURCE = "official"
CONTRACT_VERIFIED_AT = "2026-09-03"
CONTRACT_VERIFIED = True
PKCE_USED = False
PKCE_NOTE = "Kuaishou OAuth uses app_id/app_secret authorization code; PKCE is not part of the official token exchange."

AUTHORIZE_URL = "https://open.kuaishou.com/oauth2/authorize"
TOKEN_URL = "https://open.kuaishou.com/oauth2/access_token"
REFRESH_URL = "https://open.kuaishou.com/oauth2/refresh_token"
API_BASE = "https://open.kuaishou.com"
START_UPLOAD = "/openapi/photo/start_upload"
PUBLISH = "/openapi/photo/publish"
USER_INFO = "/openapi/user_info"
PHOTO_INFO = "/openapi/photo/info"

# Official Kuaishou upload helper: whole-file /api/upload below 10MB; fragment otherwise.
WHOLE_FILE_LIMIT = 10 * 1024 * 1024
