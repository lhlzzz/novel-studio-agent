"""Xiaole / Lechuang contract status. Image verified; video documented until live success."""

from creative.providers.lechuang.client import (
    IMAGE_CONTRACT_VERIFIED,
    IMAGE_ENDPOINT,
    VIDEO_CONTRACT_VERIFIED,
    VIDEO_CREATE_ENDPOINT,
    VIDEO_NOT_VERIFIED,
    LechuangClient,
)


def contract_status(client: LechuangClient | None = None) -> dict:
    client = client or LechuangClient()
    ready, reason = client.live_ready()
    return {
        "verified": bool(client.contract_verified and IMAGE_CONTRACT_VERIFIED),
        "image_verified": bool(IMAGE_CONTRACT_VERIFIED),
        "video_verified": bool(VIDEO_CONTRACT_VERIFIED),
        "ready": ready,
        "reason": reason,
        "video_reason": VIDEO_NOT_VERIFIED,
        "protocol": "openai-compatible",
        "endpoint": IMAGE_ENDPOINT,
        "video_endpoint": VIDEO_CREATE_ENDPOINT,
        "video_documented": True,
    }
