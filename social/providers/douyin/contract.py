"""Douyin Open Platform official endpoints used by this adapter."""

AUTHORIZE_URL = "https://open.douyin.com/platform/oauth/connect"
TOKEN_URL = "https://open.douyin.com/oauth/access_token/"
REFRESH_URL = "https://open.douyin.com/oauth/refresh_token/"
RENEW_REFRESH_URL = "https://open.douyin.com/oauth/renew_refresh_token/"
USERINFO_URL = "https://open.douyin.com/oauth/userinfo/"
API_BASE = "https://open.douyin.com"
UPLOAD_VIDEO = "/api/douyin/v1/video/upload_video/"
INIT_PART = "/api/douyin/v1/video/init_video_part_upload/"
UPLOAD_PART = "/api/douyin/v1/video/upload_video_part/"
COMPLETE_PART = "/api/douyin/v1/video/complete_video_part_upload/"
CREATE_VIDEO = "/api/douyin/v1/video/create_video/"
CREATE_IMAGE_TEXT = "/api/douyin/v1/video/create_image_text/"
VIDEO_DATA = "/api/douyin/v1/video/video_data/"
VIDEO_LIST = "/api/douyin/v1/video/video_list/"
SMALL_UPLOAD_LIMIT = 10 * 1024 * 1024
PART_SIZE = 5 * 1024 * 1024
