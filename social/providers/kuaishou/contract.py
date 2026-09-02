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
