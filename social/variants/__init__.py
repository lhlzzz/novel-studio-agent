"""Platform variants are derived from ContentPackage. They never leak platform APIs back into the package."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from content.models import ContentPackage
from content.variants import build_variant
from integrations.contracts.distribution import ContentVariant
from social.media_policy import policy_for


@dataclass(frozen=True)
class PlatformVariant:
    platform: str
    variant: ContentVariant
    content_type: str = ""
    account_id: str = ""
    provider: str = ""
    cover_asset: str | None = None
    platform_options: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.account_id:
            object.__setattr__(self, "account_id", self.variant.account_id)
        if not self.provider:
            object.__setattr__(self, "provider", self.platform)
        if self.platform_options is None:
            object.__setattr__(self, "platform_options", dict((self.variant.metadata or {}).get("platform_options") or {}))


class XVariant(PlatformVariant):
    platform = "x"


class InstagramVariant(PlatformVariant):
    platform = "instagram"


class YouTubeVariant(PlatformVariant):
    platform = "youtube"


class TikTokVariant(PlatformVariant):
    platform = "tiktok"


class LinkedInVariant(PlatformVariant):
    platform = "linkedin"


class XHSVariant(PlatformVariant):
    platform = "xiaohongshu"


class DouyinVariant(PlatformVariant):
    platform = "douyin"


class KuaishouVariant(PlatformVariant):
    platform = "kuaishou"


class XianyuListingVariant(PlatformVariant):
    platform = "xianyu"


VARIANT_TYPES = {
    "x": XVariant,
    "instagram": InstagramVariant,
    "youtube": YouTubeVariant,
    "tiktok": TikTokVariant,
    "linkedin": LinkedInVariant,
    "xiaohongshu": XHSVariant,
    "xhs": XHSVariant,
    "douyin": DouyinVariant,
    "kuaishou": KuaishouVariant,
    "xianyu": XianyuListingVariant,
}


def _apply_policy(variant: ContentVariant, platform: str) -> ContentVariant:
    policy = policy_for(platform)
    if policy is None:
        return variant
    title = variant.title
    if policy.title_limit and title and len(title) > policy.title_limit:
        title = title[: policy.title_limit]
    body = variant.body
    if policy.caption_limit and body and len(body) > policy.caption_limit:
        body = body[: policy.caption_limit]
    caption = variant.caption or body
    if policy.caption_limit and caption and len(caption) > policy.caption_limit:
        caption = caption[: policy.caption_limit]
    metadata = dict(variant.metadata or {})
    metadata["platform"] = platform
    metadata["content_type"] = metadata.get("content_type") or _content_type(platform, variant)
    return replace(variant, title=title, body=body, caption=caption, metadata=metadata)


def _content_type(platform: str, variant: ContentVariant) -> str:
    media = list(variant.media or ())
    if platform in {"xiaohongshu", "xhs"}:
        if any(item.lower().endswith((".mp4", ".mov")) for item in media):
            return "NOTE_VIDEO"
        return "NOTE_IMAGE"
    if platform == "douyin":
        if any(item.lower().endswith((".mp4", ".mov")) for item in media):
            return "VIDEO"
        return "IMAGE"
    if platform == "kuaishou":
        return "VIDEO"
    if platform == "xianyu":
        return "listing"
    return variant.format or "post"


class XHSVariantBuilder:
    def build(self, package: ContentPackage, *, account_id: str) -> XHSVariant:
        variant = _apply_policy(build_variant(package, account_id=account_id, platform="xiaohongshu"), "xiaohongshu")
        content_type = str((variant.metadata or {}).get("content_type") or "NOTE_IMAGE")
        cover = (variant.metadata or {}).get("cover") or (variant.metadata or {}).get("cover_asset")
        return XHSVariant(platform="xiaohongshu", variant=variant, content_type=content_type, cover_asset=cover)


class DouyinVariantBuilder:
    def build(self, package: ContentPackage, *, account_id: str) -> DouyinVariant:
        variant = _apply_policy(build_variant(package, account_id=account_id, platform="douyin"), "douyin")
        return DouyinVariant(platform="douyin", variant=variant, content_type=str((variant.metadata or {}).get("content_type") or "VIDEO"))


class KuaishouVariantBuilder:
    def build(self, package: ContentPackage, *, account_id: str) -> KuaishouVariant:
        variant = _apply_policy(build_variant(package, account_id=account_id, platform="kuaishou"), "kuaishou")
        cover = (variant.metadata or {}).get("cover")
        return KuaishouVariant(platform="kuaishou", variant=variant, content_type="VIDEO", cover_asset=cover)


class XianyuListingBuilder:
    def build(self, package: ContentPackage, *, account_id: str) -> XianyuListingVariant:
        if str(package.commerce_intent or "none") in {"", "none"}:
            raise ValueError("Xianyu listing requires explicit commerce intent")
        variant = _apply_policy(build_variant(package, account_id=account_id, platform="xianyu"), "xianyu")
        metadata = dict(variant.metadata or {})
        metadata.setdefault("listing", {
            "title": package.title,
            "description": package.body,
            "price": metadata.get("price"),
            "quantity": metadata.get("quantity") or 1,
            "category_id": metadata.get("category_id"),
            "images": list(package.media_assets),
            "cover": (list(package.media_assets) or [None])[0],
            "condition": metadata.get("condition") or "new",
            "location": metadata.get("location") or "",
            "attributes": metadata.get("attributes") or {},
            "shipping": metadata.get("shipping") or {},
        })
        variant = replace(variant, metadata=metadata)
        return XianyuListingVariant(platform="xianyu", variant=variant, content_type="listing")


BUILDERS = {
    "xiaohongshu": XHSVariantBuilder(),
    "xhs": XHSVariantBuilder(),
    "douyin": DouyinVariantBuilder(),
    "kuaishou": KuaishouVariantBuilder(),
    "xianyu": XianyuListingBuilder(),
}


def build_platform_variant(package: ContentPackage, *, account_id: str, platform: str) -> PlatformVariant:
    builder = BUILDERS.get(platform)
    if builder is not None:
        return builder.build(package, account_id=account_id)
    variant = build_variant(package, account_id=account_id, platform=platform)
    cls = VARIANT_TYPES.get(platform, PlatformVariant)
    return cls(platform=platform, variant=variant)
