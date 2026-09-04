"""Platform-specific content policies. One theme does not become one package."""

from __future__ import annotations

from typing import Any

from content.models import ContentPackage, CreativeContext


PLATFORM_POLICIES: dict[str, dict[str, Any]] = {
    "xiaohongshu": {
        "platform": "xiaohongshu",
        "format": "image_post",
        "content_type": "image_post",
        "visual": {
            "mood": "lifestyle",
            "energy": "relaxed",
            "look": "clean natural light",
        },
        "copy": {
            "needs_title": True,
            "needs_body": True,
            "needs_topics": True,
            "hook_style": "emotional_value",
        },
        "media": ("image", "cover"),
        "aspect_ratio": "3:4",
        "commerce": False,
    },
    "douyin": {
        "platform": "douyin",
        "format": "short_video",
        "content_type": "short_video",
        "visual": {
            "mood": "dynamic",
            "energy": "high",
            "look": "strong motion first 3 seconds",
        },
        "copy": {
            "needs_script": True,
            "needs_hook": True,
            "needs_shots": True,
            "needs_captions": True,
            "hook_style": "first_3_seconds",
        },
        "media": ("video", "thumbnail"),
        "aspect_ratio": "9:16",
        "commerce": False,
    },
    "kuaishou": {
        "platform": "kuaishou",
        "format": "short_video",
        "content_type": "short_video",
        "visual": {
            "mood": "direct",
            "energy": "high",
            "look": "handheld authentic",
        },
        "copy": {
            "needs_script": True,
            "needs_hook": True,
            "hook_style": "plain_spoken",
        },
        "media": ("video",),
        "aspect_ratio": "9:16",
        "commerce": False,
    },
    "weixin_video": {
        "platform": "weixin_video",
        "format": "short_video",
        "content_type": "short_video",
        "visual": {
            "mood": "warm",
            "energy": "steady",
            "look": "clean vertical",
        },
        "copy": {
            "needs_title": True,
            "needs_hook": True,
            "hook_style": "conversational",
        },
        "media": ("video", "cover"),
        "aspect_ratio": "9:16",
        "commerce": False,
    },
    "xianyu": {
        "platform": "xianyu",
        "format": "listing",
        "content_type": "listing",
        "visual": {
            "mood": "product",
            "energy": "clear",
            "look": "catalog truthful",
        },
        "copy": {
            "needs_title": True,
            "needs_body": True,
            "hook_style": "listing",
        },
        "media": ("image",),
        "aspect_ratio": "1:1",
        "commerce": True,
    },
}


def platform_policy(platform: str) -> dict[str, Any]:
    policy = PLATFORM_POLICIES.get(platform)
    if policy is None:
        raise ValueError(f"unsupported platform policy: {platform}")
    return dict(policy)


def differentiate_package(package: ContentPackage, context: CreativeContext) -> ContentPackage:
    policy = platform_policy(context.platform)
    metadata = dict(package.metadata or {})
    metadata.update({
        "platform": context.platform,
        "account_id": context.account_id,
        "character_id": context.character_id,
        "world_id": context.world_id,
        "series_id": context.series_id,
        "episode_id": context.episode_id,
        "creative_context_id": context.context_id,
        "platform_policy": policy,
        "character_context": dict(context.character_context),
        "world_context": dict(context.world_context),
        "resolved_target": dict(context.resolved_target),
    })
    copy_rules = policy.get("copy") or {}
    hook = package.hook
    if not hook and copy_rules.get("needs_hook"):
        hook = str((context.platform_context.get("copy") or {}).get("hook_style") or context.creative_request)
    title = package.title
    body = package.body
    if context.platform == "xiaohongshu":
        title = title or context.creative_request[:20]
        body = body or context.normalized_prompt
    elif context.platform == "douyin":
        title = title or context.creative_request[:30]
        body = _script_body(context)
        hook = hook or "前3秒动作"
    elif context.platform == "xianyu":
        title = title or context.creative_request[:60]
        body = body or context.normalized_prompt
        metadata["commerce_intent"] = metadata.get("commerce_intent") or "listing"
    return ContentPackage(
        package_id=package.package_id,
        title=title,
        body=body,
        content_type=str(policy.get("content_type") or package.content_type),
        evidence_ids=package.evidence_ids,
        brand_id=package.brand_id,
        creator_id=package.creator_id,
        campaign_id=package.campaign_id or context.campaign_id,
        topic=package.topic,
        content_pillar=package.content_pillar,
        hook=hook,
        format=str(policy.get("format") or package.format),
        audience=package.audience or str((context.world_context or {}).get("audience") or ""),
        caption=package.caption or body,
        media_assets=package.media_assets,
        commerce_intent="listing" if policy.get("commerce") else package.commerce_intent,
        variants=(context.platform,),
        created_at=package.created_at,
        updated_at=package.updated_at,
        metadata=metadata,
        account_id=context.account_id,
        series_id=context.series_id,
        episode_id=context.episode_id,
        platform=context.platform,
        status=package.status,
        character_id=context.character_id,
        world_id=context.world_id,
        creative_context_id=context.context_id,
        revision=package.revision,
    )


def _script_body(context: CreativeContext) -> str:
    hook = context.creative_request or context.user_request
    return (
        f"Hook: {hook}\n"
        f"Shot 1: {context.normalized_prompt}\n"
        "Action: keep motion in the first 3 seconds.\n"
        "Captions: short on-screen lines.\n"
        "BGM: high-energy but not generic EDM."
    )
