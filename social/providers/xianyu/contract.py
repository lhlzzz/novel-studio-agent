"""Xianyu Idle ISV contract. Unverified bytes upload stays fail-closed."""

CONTRACT_VERSION = "2026-09-03"
CONTRACT_SOURCE = "official"
CONTRACT_VERIFIED_AT = "2026-09-03"
CONTRACT_VERIFIED = True
PKCE_USED = False
PKCE_NOTE = "Taobao/Xianyu OAuth uses client_id/client_secret authorization code; PKCE is not part of the official token exchange."

AUTHORIZE_URL = "https://oauth.taobao.com/authorize"
TOKEN_URL = "https://oauth.taobao.com/token"
ROUTER = "https://eco.taobao.com/router/rest"
METHODS = {
    "authorize": "alibaba.idle.isv.user.authorize",
    "user_info": "alibaba.idle.isv.user.info",
    "media_upload": "alibaba.idle.isv.media.upload",
    "item_publish": "alibaba.idle.isv.item.publish",
    "item_edit": "alibaba.idle.isv.item.edit",
    "item_downshelf": "alibaba.idle.isv.item.downshelf",
    "item_query": "alibaba.idle.isv.item.query",
}

# Official idle.isv.media.upload is URL-based. Local bytes upload is not contract-verified.
MEDIA_UPLOAD_BYTES_CONTRACT_VERIFIED = False
MEDIA_UPLOAD_MODE = "url"
