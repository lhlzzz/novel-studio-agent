"""Build platform-specific content variants without leaking constraints into ContentPackage."""

from __future__ import annotations

from content.models import ContentPackage
from integrations.contracts.distribution import ContentVariant

PLATFORM_CONSTRAINTS = {
    "x": {"max_chars": 280, "hashtag_limit": 3},
    "linkedin": {"max_chars": 3000, "hashtag_limit": 8},
    "instagram": {"max_chars": 2200, "hashtag_limit": 30},
    "youtube": {"max_chars": 5000, "hashtag_limit": 15},
    "tiktok": {"max_chars": 2200, "hashtag_limit": 20},
    "xiaohongshu": {"max_chars": 1000, "hashtag_limit": 10, "title_limit": 20},
    "douyin": {"max_chars": 1000, "hashtag_limit": 5, "title_limit": 30},
    "kuaishou": {"max_chars": 500, "hashtag_limit": 5},
    "xianyu": {"max_chars": 5000, "hashtag_limit": 0, "title_limit": 60},
}


def build_variant(package: ContentPackage, *, account_id: str | None = None, platform: str, integration_id: str | None = None) -> ContentVariant:
    account_id = account_id or integration_id or ""
    constraints = dict(PLATFORM_CONSTRAINTS.get(platform, {"max_chars": 2000, "hashtag_limit": 5}))
    metadata = dict(package.metadata or {})
    hashtags = tuple(metadata.get("hashtags") or ())
    limit = int(constraints.get("hashtag_limit") or 0)
    if limit:
        hashtags = hashtags[:limit]
    body = package.body
    max_chars = int(constraints.get("max_chars") or 0)
    if max_chars and len(body) > max_chars:
        body = body[: max_chars - 1].rstrip() + "..."
    media = tuple(package.media_assets or metadata.get("media") or ())
    caption = package.caption or body
    return ContentVariant(
        account_id=account_id,
        body=body,
        media=media,
        metadata={**metadata, "platform": platform, "settings": dict(metadata.get("settings") or {})},
        title=package.title,
        hashtags=hashtags,
        cta=str(metadata.get("cta") or ""),
        constraints=constraints,
        caption=caption,
        hook=package.hook,
        format=package.format or package.content_type,
    )
