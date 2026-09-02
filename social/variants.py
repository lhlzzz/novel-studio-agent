"""Platform variants are derived from ContentPackage. They never leak platform APIs back into the package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from content.models import ContentPackage
from content.variants import build_variant
from integrations.contracts.distribution import ContentVariant


@dataclass(frozen=True)
class PlatformVariant:
    platform: str
    variant: ContentVariant

    @property
    def account_id(self) -> str:
        return self.variant.account_id


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


VARIANT_TYPES = {
    "x": XVariant,
    "instagram": InstagramVariant,
    "youtube": YouTubeVariant,
    "tiktok": TikTokVariant,
    "linkedin": LinkedInVariant,
}


def build_platform_variant(package: ContentPackage, *, account_id: str, platform: str) -> PlatformVariant:
    variant = build_variant(package, account_id=account_id, platform=platform)
    cls = VARIANT_TYPES.get(platform, PlatformVariant)
    return cls(platform=platform, variant=variant)
