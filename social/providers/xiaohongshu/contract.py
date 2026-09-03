"""Xiaohongshu official surface.

OAuth architecture exists on the open platform. write_notes / direct server
publish is not live-verified and stays HANDOFF_ONLY until official write
access is confirmed.
"""

from __future__ import annotations

import os

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

# Official method inventory from the current open-platform OAuth surface.
# Endpoints stay empty until an operator-configured official URL is supplied.
# write_notes remains planned / manual-review; direct publish stays blocked.
OFFICIAL_METHODS = (
    "auth_info",
    "authorize",
    "access_token",
    "refresh_token",
    "token_status",
    "batch_get_min_user_info",
    "auth_app/list",
    "auth_app/remove",
)
OFFICIAL_SCOPES = {
    "basic_info": "open",
    "write_notes": "planned_or_manual_review",
}

# Unverified. Do not call these until OAUTH_CONTRACT_VERIFIED is true.
AUTHORIZE_URL = os.getenv("XHS_AUTHORIZE_URL", "").strip()
TOKEN_URL = os.getenv("XHS_TOKEN_URL", "").strip()
REFRESH_URL = os.getenv("XHS_REFRESH_URL", "").strip()
TOKEN_STATUS_URL = os.getenv("XHS_TOKEN_STATUS_URL", "").strip()
USERINFO_URL = os.getenv("XHS_USERINFO_URL", "").strip()
