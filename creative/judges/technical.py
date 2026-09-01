"""Local technical QA. File integrity only; never a visual quality score."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from creative.errors import TechnicalMediaError
from creative.schemas import MediaAsset


class TechnicalQA:
    name = "technical"

    def inspect_image(self, asset: MediaAsset) -> dict[str, Any]:
        failures = []
        path = Path(asset.path) if asset.path else None
        if path is None or not path.is_file():
            return {"decision": "fail", "failures": ["missing_file"]}
        try:
            from PIL import Image
            with Image.open(path) as image:
                width, height = image.size
                fmt = (image.format or "").lower()
        except Exception:
            return {"decision": "fail", "failures": ["unreadable"]}
        mime = asset.mime_type or ""
        if mime and not mime.startswith("image/") and asset.type == "image":
            failures.append("format")
        if asset.size <= 0 and path.stat().st_size <= 0:
            failures.append("size")
        if width <= 0 or height <= 0:
            failures.append("resolution")
        return {
            "decision": "pass" if not failures else "fail",
            "failures": failures,
            "width": width,
            "height": height,
            "mime": mime or f"image/{fmt or 'png'}",
            "filesize": path.stat().st_size,
            "aspect_ratio": round(width / max(height, 1), 4),
            "format": fmt,
        }

    def inspect_video(self, asset: MediaAsset) -> dict[str, Any]:
        failures = []
        path = Path(asset.path) if asset.path else None
        if path is None or not path.is_file():
            return {"decision": "fail", "failures": ["missing_file"]}
        try:
            from creative.render.ffmpeg import video_info
            info = video_info(path)
        except TechnicalMediaError:
            return {"decision": "fail", "failures": ["unreadable"]}
        if not info.get("codec"):
            failures.append("codec")
        if info.get("filesize", 0) <= 0:
            failures.append("file_size")
        if not info.get("width") or not info.get("height"):
            failures.append("resolution")
        if info.get("duration") is not None and float(info.get("duration") or 0) <= 0:
            failures.append("duration")
        return {
            "decision": "pass" if not failures else "fail",
            "failures": failures,
            **info,
        }
