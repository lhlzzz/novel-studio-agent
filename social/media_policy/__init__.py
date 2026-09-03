"""Platform media/content policy from current official documentation.

Values are claimed platform limits, not "verified because the docs exist".
Publish Gate still requires a runtime-verified account and capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from integrations.contracts.distribution import DistributionJob


@dataclass(frozen=True)
class PlatformMediaPolicy:
    platform: str
    max_size_bytes: int
    mime: tuple[str, ...]
    duration_seconds: tuple[float, float] | None
    resolution: tuple[int, int] | None
    aspect_ratio: tuple[str, ...]
    image_count: tuple[int, int]
    video_count: tuple[int, int]
    cover_required: bool
    title_limit: int
    caption_limit: int
    extra: dict[str, Any]


# Xiaohongshu share SDK: image notes 1-18 images; video notes 1 video + 0-1 cover.
XIAOHONGSHU = PlatformMediaPolicy(
    platform="xiaohongshu",
    max_size_bytes=128 * 1024 * 1024,
    mime=("image/jpeg", "image/png", "image/webp", "video/mp4"),
    duration_seconds=(1, 15 * 60),
    resolution=None,
    aspect_ratio=("3:4", "1:1", "16:9", "9:16"),
    image_count=(1, 18),
    video_count=(0, 1),
    cover_required=False,
    title_limit=20,
    caption_limit=1000,
    extra={"content_types": ("NOTE_IMAGE", "NOTE_VIDEO", "image_note", "video_note")},
)

# Douyin Open Platform video/image publish. Brand logo/watermark is a review risk.
DOUYIN = PlatformMediaPolicy(
    platform="douyin",
    max_size_bytes=4 * 1024 * 1024 * 1024,
    mime=("video/mp4", "video/quicktime", "image/jpeg", "image/png"),
    duration_seconds=(3, 60 * 60),
    resolution=None,
    aspect_ratio=("9:16", "16:9", "1:1"),
    image_count=(0, 35),
    video_count=(0, 1),
    cover_required=False,
    title_limit=30,
    caption_limit=1000,
    extra={
        "watermark_forbidden": True,
        "logo_review_risk": True,
        "content_types": ("VIDEO", "IMAGE"),
        "chunk_suggested_bytes": 50 * 1024 * 1024,
        "chunk_required_bytes": 128 * 1024 * 1024,
    },
)

# Kuaishou user_video_publish: start_upload -> upload -> publish. Cover optional.
KUAISHOU = PlatformMediaPolicy(
    platform="kuaishou",
    max_size_bytes=4 * 1024 * 1024 * 1024,
    mime=("video/mp4", "image/jpeg", "image/png"),
    duration_seconds=(3, 60 * 60),
    aspect_ratio=("9:16", "16:9", "1:1"),
    resolution=None,
    image_count=(0, 1),
    video_count=(1, 1),
    cover_required=False,
    title_limit=0,
    caption_limit=500,
    extra={"merchant_product_id": False, "content_types": ("VIDEO",)},
)

# Xianyu idle item: listing images, not a social feed post.
XIANYU = PlatformMediaPolicy(
    platform="xianyu",
    max_size_bytes=5 * 1024 * 1024,
    mime=("image/jpeg", "image/png"),
    duration_seconds=None,
    resolution=None,
    aspect_ratio=("1:1", "3:4", "4:3"),
    image_count=(1, 10),
    video_count=(0, 0),
    cover_required=True,
    title_limit=60,
    caption_limit=5000,
    extra={"content_types": ("listing",), "video_not_default": True},
)

POLICIES = {
    "xiaohongshu": XIAOHONGSHU,
    "xhs": XIAOHONGSHU,
    "douyin": DOUYIN,
    "kuaishou": KUAISHOU,
    "xianyu": XIANYU,
}


def policy_for(platform: str) -> PlatformMediaPolicy | None:
    return POLICIES.get(platform)


def validate_job(job: DistributionJob, *, platform: str | None = None) -> list[str]:
    platform = platform or job.platform or ""
    policy = policy_for(platform)
    if policy is None:
        return []
    errors: list[str] = []
    title = job.variant.title or ""
    caption = job.variant.caption or job.variant.body or ""
    if policy.title_limit and title and len(title) > policy.title_limit:
        errors.append(f"{platform} title exceeds {policy.title_limit} characters")
    if policy.caption_limit and len(caption) > policy.caption_limit:
        errors.append(f"{platform} caption exceeds {policy.caption_limit} characters")
    media = list(job.variant.media or ())
    images = [path for path in media if _looks_image(path)]
    videos = [path for path in media if _looks_video(path)]
    if images and not (policy.image_count[0] <= len(images) <= policy.image_count[1]):
        errors.append(f"{platform} image count must be {policy.image_count[0]}..{policy.image_count[1]}")
    if videos and not (policy.video_count[0] <= len(videos) <= policy.video_count[1]):
        errors.append(f"{platform} video count must be {policy.video_count[0]}..{policy.video_count[1]}")
    if policy.extra.get("watermark_forbidden"):
        metadata = job.variant.metadata or {}
        if metadata.get("watermark") or metadata.get("logo"):
            errors.append(f"{platform} watermark/logo is a policy risk and is blocked")
    for path in media:
        file = Path(path)
        if file.exists() and file.stat().st_size > policy.max_size_bytes:
            errors.append(f"{platform} media exceeds max size: {path}")
    if platform == "xianyu":
        metadata = job.variant.metadata or {}
        listing = metadata.get("listing") or {}
        if metadata.get("commerce_intent", "none") in {"", "none", None} and not listing:
            errors.append("xianyu listing requires explicit commerce intent")
        if listing and listing.get("price") in {None, "", 0, "0"}:
            errors.append("xianyu listing price is required")
        if listing and not listing.get("category_id"):
            errors.append("xianyu listing category_id is required")
    return errors


def _looks_image(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in {".jpg", ".jpeg", ".png", ".webp"} or "image" in path


def _looks_video(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in {".mp4", ".mov", ".quicktime"} or "video" in path
