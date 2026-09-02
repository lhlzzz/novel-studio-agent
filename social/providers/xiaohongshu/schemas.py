from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class XHSNotePackage:
    platform: str = "xiaohongshu"
    content_type: str = "image_note"
    title: str = ""
    content: str = ""
    hashtags: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    video: str | None = None
    cover: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_export(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "content_type": self.content_type,
            "title": self.title,
            "content": self.content,
            "hashtags": list(self.hashtags),
            "images": list(self.images),
            "video": self.video,
            "cover": self.cover,
        }
