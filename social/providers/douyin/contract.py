"""Douyin Open Platform official endpoints used by this adapter."""

CONTRACT_VERSION = "2026-09-03"
CONTRACT_SOURCE = "official"
CONTRACT_VERIFIED_AT = "2026-09-03"
CONTRACT_VERIFIED = True
PKCE_USED = False
PKCE_NOTE = "Douyin OAuth uses client_key/client_secret authorization code; PKCE is not part of the official token exchange."

AUTHORIZE_URL = "https://open.douyin.com/platform/oauth/connect"
TOKEN_URL = "https://open.douyin.com/oauth/access_token/"
REFRESH_URL = "https://open.douyin.com/oauth/refresh_token/"
RENEW_REFRESH_URL = "https://open.douyin.com/oauth/renew_refresh_token/"
USERINFO_URL = "https://open.douyin.com/oauth/userinfo/"
API_BASE = "https://open.douyin.com"
UPLOAD_VIDEO = "/api/douyin/v1/video/upload_video/"
UPLOAD_IMAGE = "/api/douyin/v1/video/upload_image/"
INIT_PART = "/api/douyin/v1/video/init_video_part_upload/"
UPLOAD_PART = "/api/douyin/v1/video/upload_video_part/"
COMPLETE_PART = "/api/douyin/v1/video/complete_video_part_upload/"
CREATE_VIDEO = "/api/douyin/v1/video/create_video/"
CREATE_IMAGE_TEXT = "/api/douyin/v1/video/create_image_text/"
VIDEO_DATA = "/api/douyin/v1/video/video_data/"
VIDEO_LIST = "/api/douyin/v1/video/video_list/"
# Official: >50MB suggested chunk; >128MB required; max 4GB.
SUGGESTED_PART_LIMIT = 50 * 1024 * 1024
REQUIRED_PART_LIMIT = 128 * 1024 * 1024
MAX_VIDEO_BYTES = 4 * 1024 * 1024 * 1024
SMALL_UPLOAD_LIMIT = SUGGESTED_PART_LIMIT
PART_SIZE = 5 * 1024 * 1024
