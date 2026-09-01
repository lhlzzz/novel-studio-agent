"""Versioned creative prompts. Generation must record the version used."""

from __future__ import annotations

PROMPTS = {
    ("system", "v1"): "You are Meiti creative direction. Content first. No hard sell.",
    ("workflow", "lifestyle", "v1"): "Natural lifestyle, handheld, available light, no logo lockup, no CTA overlay.",
    ("workflow", "cinematic", "v1"): "Cinematic lighting, motivated camera, shallow depth, restrained color.",
    ("workflow", "ugc", "v1"): "Handheld UGC, slightly imperfect framing, natural speech cadence, no studio gloss.",
    ("workflow", "drama", "v1"): "Short-drama continuity, locked character wardrobe, shot-to-shot geography.",
    ("node", "scene", "v1"): "Plan one shot: subject, setting, camera, motion, duration. No brand slogans.",
    ("style", "natural", "v1"): "Natural color, soft daylight, skin texture preserved, no beauty filter.",
    ("character", "v1"): "Keep identity, wardrobe, age, and hair consistent with character visual DNA.",
    ("motion", "v1"): "Subtle motion, no morphing faces, no teleporting props.",
    ("judge", "image", "v1"): "Score composition, identity, artifacts, lighting, aesthetic, content fit.",
    ("judge", "video", "v1"): "Score motion, identity, temporal stability, camera, visual quality, platform fit.",
}


def get_prompt(*parts: str, version: str = "v1") -> str:
    key = tuple(parts) + (version,)
    if key not in PROMPTS:
        raise KeyError(key)
    return PROMPTS[key]


def render_scene_prompt(brief: dict) -> str:
    face = "Do not show a recognizable face." if not brief.get("face_visible") else "Face may appear naturally."
    product = "Product is optional and must stay background." if brief.get("commerce_intent") in {None, "", "none"} else "Product may appear only if it serves the story."
    return (
        f"{get_prompt('workflow', str(brief.get('style_key') or 'lifestyle'))} "
        f"Brief: {brief.get('brief') or brief.get('text') or ''}. "
        f"Aspect {brief.get('aspect_ratio') or '9:16'}, duration {brief.get('duration_seconds') or 15}s, "
        f"camera {brief.get('camera') or 'static'}, motion {brief.get('motion') or 'subtle'}. "
        f"{face} {product}"
    )
