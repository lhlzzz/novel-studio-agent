"""Content owned by Meiti and independent from distribution jobs."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContentPackage:
    package_id: str
    title: str
    body: str
    content_type: str = "post"
    evidence_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
