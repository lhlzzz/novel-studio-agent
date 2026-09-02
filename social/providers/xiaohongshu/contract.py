"""Xiaohongshu official surface.

OAuth architecture exists on the open platform. write_notes / direct server
publish is not live-verified and stays HANDOFF_ONLY until official write
access is confirmed.
"""

CONTRACT_VERSION = "2026-09-03"
CONTRACT_SOURCE = "official"
CONTRACT_VERIFIED_AT = "2026-09-03"
CONTRACT_VERIFIED = True
OAUTH_ARCHITECTURE_SUPPORTED = True
OAUTH_CONTRACT_VERIFIED = False
WRITE_NOTES_AVAILABLE = False
PKCE_USED = False
PKCE_NOTE = "XHS server OAuth exists as a product capability; token endpoints are not extracted into this runtime, so PKCE is not claimed."

HANDOFF_ONLY = True
DIRECT_PUBLISH_AVAILABLE = False
SHARE_IMAGE_MIN = 1
SHARE_IMAGE_MAX = 18
SHARE_VIDEO_COUNT = 1
SHARE_COVER_MAX = 1

# Unverified. Do not call these until OAUTH_CONTRACT_VERIFIED is true.
AUTHORIZE_URL = ""
TOKEN_URL = ""
