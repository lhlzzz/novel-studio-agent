"""Memory contracts. Operational facts stay scoped; knowledge is a document, not a blob."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content.models import utcnow


SCOPE_TYPES = (
    "GLOBAL",
    "PLATFORM",
    "ACCOUNT",
    "CHARACTER",
    "WORLD",
    "SERIES",
    "EPISODE",
    "CAMPAIGN",
    "PUBLICATION",
    "ANALYTICS",
)

SOURCE_TYPES = (
    "operational",
    "obsidian",
    "retrieval",
    "analytics",
    "creative",
    "publication",
    "research",
    "user",
    "system",
)

LEARNING_KINDS = (
    "WHAT_WORKED",
    "WHAT_FAILED",
    "CREATIVE_LEARNING",
    "PLATFORM_LEARNING",
    "AUDIENCE_LEARNING",
    "PRODUCTION_LEARNING",
    "ANALYTICS_LEARNING",
)


@dataclass(frozen=True)
class MemoryFact:
    fact_id: str
    namespace: str
    subject: str
    value: Any
    source: str
    confidence: float = 1.0
    account_id: str | None = None
    platform: str = ""
    scope_type: str = "ACCOUNT"
    scope_id: str | None = None


@dataclass(frozen=True)
class KnowledgeDocument:
    id: str
    scope_type: str
    title: str
    path: str
    content: str
    hash: str
    scope_id: str | None = None
    account_id: str | None = None
    platform: str = ""
    source_type: str = "obsidian"
    tags: tuple[str, ...] = ()
    created_at: str | None = None
    updated_at: str | None = None
    version: int = 1
    status: str = "ACTIVE"
    character_id: str | None = None
    world_id: str | None = None
    series_id: str | None = None
    episode_id: str | None = None
    publication_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.scope_type not in SCOPE_TYPES:
            raise ValueError(f"invalid knowledge scope: {self.scope_type}")
        if self.scope_type != "GLOBAL" and not self.account_id and self.scope_type not in {"PLATFORM", "GLOBAL"}:
            raise ValueError("account-scoped knowledge requires account_id")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)


@dataclass(frozen=True)
class MemoryHit:
    document: KnowledgeDocument
    score: float
    origin: str
