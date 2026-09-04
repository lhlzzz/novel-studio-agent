"""Platform character / world / creative DNA. Policy is not enough."""

from __future__ import annotations

from typing import Any

from content.models import AccountWorld, PlatformCreativeDNA, VirtualCharacter
from content.platform_policy import platform_policy


PLATFORM_CREATIVE_DEFAULTS: dict[str, dict[str, Any]] = {
    "xiaohongshu": {
        "visual_style": {"look": "candid smartphone lifestyle", "grain": "natural", "grade": "soft daylight"},
        "copy_style": {"voice": "intimate diary", "length": "caption plus topics"},
        "hook_style": "emotional_value",
        "camera_style": "eye-level handheld phone",
        "motion_style": "still-to-subtle",
        "emotion_style": "quiet competence",
        "audience_relationship": "peer sharing a real day",
        "cta_style": "none",
        "content_frequency": "daily image",
        "prompt_dna": {
            "authenticity": "real skin texture, no beauty filter, no studio gloss",
            "composition": "slightly imperfect 3:4 frame",
            "negative": "stock photo, luxury catalog, identical pose reuse, beauty filter",
        },
    },
    "douyin": {
        "visual_style": {"look": "high-energy vertical", "grain": "crisp", "grade": "punchy contrast"},
        "copy_style": {"voice": "spoken hook", "length": "on-screen lines"},
        "hook_style": "first_3_seconds",
        "camera_style": "push-in handheld",
        "motion_style": "action first three seconds",
        "emotion_style": "drive",
        "audience_relationship": "coach in motion",
        "cta_style": "watch-through",
        "content_frequency": "daily short video",
        "prompt_dna": {
            "authenticity": "real sweat and motion, no cinematic fake slow-mo unless requested",
            "composition": "9:16 subject-centered with motion headroom",
            "negative": "static slideshow, reused still as video, watermark, beauty filter",
        },
    },
    "kuaishou": {
        "visual_style": {"look": "handheld authentic", "grain": "raw", "grade": "unpolished"},
        "copy_style": {"voice": "plain spoken", "length": "direct"},
        "hook_style": "plain_spoken",
        "camera_style": "chest-height handheld",
        "motion_style": "walk and talk",
        "emotion_style": "direct",
        "audience_relationship": "neighbor showing work",
        "cta_style": "none",
        "content_frequency": "daily short video",
        "prompt_dna": {
            "authenticity": "unpolished lighting, real location noise",
            "composition": "9:16 close enough to feel present",
            "negative": "luxury ad, studio cyclorama, reused still as video",
        },
    },
    "weixin_video": {
        "visual_style": {"look": "warm vertical", "grain": "clean", "grade": "soft warm"},
        "copy_style": {"voice": "conversational", "length": "title plus hook"},
        "hook_style": "conversational",
        "camera_style": "stable vertical",
        "motion_style": "steady",
        "emotion_style": "warm",
        "audience_relationship": "familiar acquaintance",
        "cta_style": "none",
        "content_frequency": "regular short video",
        "prompt_dna": {
            "authenticity": "clean but not commercial",
            "composition": "9:16 with readable face",
            "negative": "harsh flash, meme overlay, reused still as video",
        },
    },
    "xianyu": {
        "visual_style": {"look": "catalog truthful", "grain": "clear", "grade": "neutral"},
        "copy_style": {"voice": "listing", "length": "facts first"},
        "hook_style": "listing",
        "camera_style": "front product",
        "motion_style": "none",
        "emotion_style": "clear",
        "audience_relationship": "seller to buyer",
        "cta_style": "listing",
        "content_frequency": "listing images",
        "prompt_dna": {
            "authenticity": "true color, true condition, no staging that hides defects",
            "composition": "1:1 product-centered",
            "negative": "beauty retouch that hides wear, stock background swap",
        },
    },
}


def default_creative_dna(platform: str) -> dict[str, Any]:
    payload = dict(PLATFORM_CREATIVE_DEFAULTS.get(platform) or {})
    policy = platform_policy(platform)
    visual = dict(payload.get("visual_style") or {})
    visual.update(policy.get("visual") or {})
    payload["visual_style"] = visual
    payload.setdefault("hook_style", str((policy.get("copy") or {}).get("hook_style") or ""))
    payload.setdefault("asset_freshness_policy", "NEW_PRIMARY_ASSET_REQUIRED")
    return payload


def character_lock_prompt(character: VirtualCharacter | None) -> str:
    if character is None:
        return ""
    appearance = dict(character.appearance_profile or {})
    body = dict(character.body_profile or {})
    face = dict(character.face_profile or {})
    hair = dict(character.hair_profile or {})
    skin = dict(character.skin_profile or {})
    clothing = dict(character.clothing_profile or {})
    personality = dict(character.personality_profile or {})
    lines = [
        "CHARACTER LOCK",
        f"Identity: {character.name}. Keep this exact person.",
        f"Fixed age range: {character.age_range or appearance.get('age_range') or 'unchanged'}.",
        f"Fixed face: {_join(face) or 'same face geometry, no drift'}.",
        f"Fixed hair: {_join(hair) or 'same haircut and color'}.",
        f"Fixed skin: {_join(skin) or 'same skin tone and texture'}.",
        f"Fixed body: {_join(body) or 'same body type'}.",
        f"Fixed presence: {_join(appearance) or character.platform_personality or 'same overall temperament'}.",
        f"Fixed clothing tendency: {_join(clothing) or 'same wardrobe family'}.",
        f"Fixed accessories: {', '.join(character.accessories) if character.accessories else 'keep established accessories'}.",
        f"Fixed personality: {_join(personality) or character.speaking_style or 'same character voice'}.",
    ]
    if character.occupation:
        lines.append(f"Occupation: {character.occupation}.")
    if character.location:
        lines.append(f"Lives in: {character.location}.")
    if character.forbidden_changes:
        lines.append("Prohibited changes: " + "; ".join(character.forbidden_changes) + ".")
    if character.continuity_rules:
        lines.append("Continuity rules: " + _join(character.continuity_rules) + ".")
    return "\n".join(lines)


def world_lock_prompt(world: AccountWorld | None) -> str:
    if world is None:
        return ""
    visual = dict(world.visual_language or {})
    lines = [
        "WORLD LOCK",
        f"World: {world.name}.",
        f"City: {world.city or visual.get('city') or 'keep established city'}.",
        f"Places: {', '.join(world.locations) if world.locations else 'keep established locations'}.",
        f"Spaces: {world.world_description or world.core_theme or 'keep established spaces'}.",
        f"Time of day: {world.time_of_day or visual.get('time') or 'keep established daily rhythm'}.",
        f"Season: {world.season or visual.get('season') or 'keep established season'}.",
        f"Weather / light: {world.lighting or visual.get('light') or 'keep established lighting'}.",
        f"Lifestyle: {world.lifestyle or ', '.join(world.daily_life_rules) or 'keep established lifestyle'}.",
        f"Photography environment: {_join(visual) or world.tone or 'keep established photographic world'}.",
    ]
    if world.social_relations:
        lines.append("Social relations: " + ", ".join(world.social_relations) + ".")
    if world.taboos:
        lines.append("Taboos: " + "; ".join(world.taboos) + ".")
    return "\n".join(lines)


def dna_from_character(character: VirtualCharacter) -> dict[str, Any]:
    payload = dict(character.character_dna or {})
    payload.update({
        "identity": character.name,
        "appearance": dict(character.appearance_profile),
        "body": dict(character.body_profile),
        "face": dict(character.face_profile),
        "hair": dict(character.hair_profile),
        "skin": dict(character.skin_profile),
        "age_range": character.age_range,
        "occupation": character.occupation,
        "location": character.location,
        "personality": dict(character.personality_profile),
        "values": list(character.values),
        "behavior": character.behavior,
        "speech": character.speech or character.speaking_style,
        "style": dict(character.style),
        "clothing": dict(character.clothing_profile),
        "accessories": list(character.accessories),
        "photography": character.photography,
        "lighting": character.lighting,
        "platform_personality": character.platform_personality,
        "content_behavior": character.content_behavior,
        "audience_relationship": character.audience_relationship,
        "continuity_rules": dict(character.continuity_rules),
        "prohibited_changes": list(character.forbidden_changes),
    })
    return payload


def dna_from_world(world: AccountWorld) -> dict[str, Any]:
    payload = dict(world.world_dna or {})
    payload.update({
        "name": world.name,
        "city": world.city,
        "locations": list(world.locations),
        "season": world.season,
        "time": world.time_of_day,
        "lighting": world.lighting,
        "lifestyle": world.lifestyle,
        "social_relations": list(world.social_relations),
        "visual_language": dict(world.visual_language),
    })
    return payload


def merge_creative_dna(account_id: str, platform: str, existing: PlatformCreativeDNA | None) -> PlatformCreativeDNA:
    defaults = default_creative_dna(platform)
    if existing is None:
        return PlatformCreativeDNA(
            dna_id=f"dna-{account_id}",
            account_id=account_id,
            platform=platform,
            visual_style=dict(defaults.get("visual_style") or {}),
            copy_style=dict(defaults.get("copy_style") or {}),
            hook_style=str(defaults.get("hook_style") or ""),
            camera_style=str(defaults.get("camera_style") or ""),
            motion_style=str(defaults.get("motion_style") or ""),
            emotion_style=str(defaults.get("emotion_style") or ""),
            audience_relationship=str(defaults.get("audience_relationship") or ""),
            cta_style=str(defaults.get("cta_style") or ""),
            content_frequency=str(defaults.get("content_frequency") or ""),
            asset_freshness_policy=str(defaults.get("asset_freshness_policy") or "NEW_PRIMARY_ASSET_REQUIRED"),
            prompt_dna=dict(defaults.get("prompt_dna") or {}),
        )
    visual = dict(defaults.get("visual_style") or {})
    visual.update(existing.visual_style or {})
    copy_style = dict(defaults.get("copy_style") or {})
    copy_style.update(existing.copy_style or {})
    prompt_dna = dict(defaults.get("prompt_dna") or {})
    prompt_dna.update(existing.prompt_dna or {})
    return PlatformCreativeDNA(
        dna_id=existing.dna_id,
        account_id=existing.account_id,
        platform=existing.platform,
        visual_style=visual,
        copy_style=copy_style,
        hook_style=existing.hook_style or str(defaults.get("hook_style") or ""),
        camera_style=existing.camera_style or str(defaults.get("camera_style") or ""),
        motion_style=existing.motion_style or str(defaults.get("motion_style") or ""),
        emotion_style=existing.emotion_style or str(defaults.get("emotion_style") or ""),
        audience_relationship=existing.audience_relationship or str(defaults.get("audience_relationship") or ""),
        cta_style=existing.cta_style or str(defaults.get("cta_style") or ""),
        content_frequency=existing.content_frequency or str(defaults.get("content_frequency") or ""),
        asset_freshness_policy=existing.asset_freshness_policy or "NEW_PRIMARY_ASSET_REQUIRED",
        prompt_dna=prompt_dna,
        created_at=existing.created_at,
        updated_at=existing.updated_at,
    )


def _join(value: Any) -> str:
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            if item in {None, ""}:
                continue
            if isinstance(item, (list, tuple, dict, set)):
                nested = _join(item)
                if nested:
                    parts.append(f"{key}={nested}")
                continue
            parts.append(f"{key}={item}")
        return ", ".join(parts)
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value if item not in {None, ""})
    return str(value or "")
