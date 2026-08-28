#!/usr/bin/env python3
"""Generate reference image for 小野 virtual sexy dancer video (black sling + black stockings style)."""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math

# Output directory
OUT = Path(__file__).resolve().parents[1] / "videos/generated-frames/xiaoye-reference"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1024, 1024
BG = (18, 18, 22)

def create_reference():
    im = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(im)

    # Background gradient effect
    for y in range(H):
        r = int(18 + (y / H) * 12)
        g = int(18 + (y / H) * 8)
        b = int(22 + (y / H) * 15)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Main character pose - sexy standing pose
    cx, cy = W // 2, H // 2 + 80

    # Black sling dress (minimal coverage)
    dress_color = (25, 25, 28)
    skin_color = (255, 228, 210)

    # Legs - black stockings
    leg_color = (20, 20, 24)

    # Draw stockings on legs
    for leg in range(2):
        x_off = -180 if leg == 0 else 180
        # Upper leg
        draw.ellipse([cx + x_off - 45, cy + 60, cx + x_off + 45, cy + 180], fill=leg_color)
        # Lower leg
        draw.ellipse([cx + x_off - 35, cy + 170, cx + x_off + 35, cy + 280], fill=leg_color)

    # Torso - black sling dress
    # Main body
    draw.ellipse([cx - 130, cy - 80, cx + 130, cy + 120], fill=dress_color, outline=(40, 40, 45), width=3)

    # Sling straps
    draw.polygon([(cx - 130, cy - 60), (cx - 85, cy - 180), (cx - 110, cy - 170)], fill=dress_color)
    draw.polygon([(cx + 130, cy - 60), (cx + 85, cy - 180), (cx + 110, cy - 170)], fill=dress_color)

    # Neck area
    draw.ellipse([cx - 35, cy - 100, cx + 35, cy - 20], fill=skin_color)

    # Head
    draw.ellipse([cx - 85, cy - 220, cx + 85, cy - 60], fill=skin_color)

    # Hair - black long hair
    hair_color = (25, 20, 18)
    draw.ellipse([cx - 95, cy - 280, cx + 95, cy - 100], fill=hair_color)

    # Face details
    draw.ellipse([cx - 55, cy - 175, cx - 25, cy - 145], fill=(220, 180, 160))  # left eye
    draw.ellipse([cx + 25, cy - 175, cx + 55, cy - 145], fill=(220, 180, 160))   # right eye

    # Eyes shine
    draw.ellipse([cx - 48, cy - 168, cx - 36, cy - 156], fill=(255, 255, 255))
    draw.ellipse([cx + 36, cy - 168, cx + 48, cy - 156], fill=(255, 255, 255))

    # Eyebrows
    draw.line([(cx - 50, cy - 155), (cx - 30, cy - 148)], fill=(200, 180, 170), width=4)
    draw.line([(cx + 30, cy - 155), (cx + 50, cy - 148)], fill=(200, 180, 170), width=4)

    # Nose
    draw.ellipse([cx - 8, cy - 140, cx + 8, cy - 128], fill=(180, 140, 130))

    # Lips
    draw.ellipse([cx - 35, cy - 120, cx + 35, cy - 100], fill=(180, 100, 110))

    # Hands - one on hip, one touching hair
    hand_size = 45
    # Right hand (touching hair)
    draw.ellipse([cx + 140, cy - 180, cx + 185, cy - 135], fill=skin_color)
    # Left hand (on hip)
    draw.ellipse([cx - 185, cy + 40, cx - 140, cy + 85], fill=skin_color)

    # High heels (black sling style)
    heel_color = (0, 0, 0)
    # Left shoe
    draw.ellipse([cx - 200, cy + 280, cx - 140, cy + 340], fill=heel_color, outline=(30, 30, 30), width=3)
    draw.polygon([(cx - 200, cy + 280), (cx - 170, cy + 340), (cx - 150, cy + 310)], fill=(30, 30, 30))
    # Right shoe
    draw.ellipse([cx + 140, cy + 280, cx + 200, cy + 340], fill=heel_color, outline=(30, 30, 30), width=3)
    draw.polygon([(cx + 200, cy + 280), (cx + 170, cy + 340), (cx + 150, cy + 310)], fill=(30, 30, 30))

    # Accent lighting
    for i in range(3):
        draw.ellipse([cx + 100 + i*20, cy - 200 + i*10, cx + 130 + i*20, cy - 170 + i*10], fill=(255, 220, 180))

    # Save reference image
    ref_path = OUT / "xiaoye_reference_v1.jpg"
    im.save(ref_path, quality=95)
    print(f"Reference image saved: {ref_path}")
    print(f"Size: {ref_path.stat().st_size / 1024:.1f}KB")

if __name__ == "__main__":
    create_reference()
