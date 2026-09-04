"""Content owned by Meiti and independent from distribution jobs."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any


ACCOUNT_PLATFORMS = (
    "xiaohongshu",
    "douyin",
    "kuaishou",
    "weixin_video",
    "xianyu",
)

PLATFORM_ACCOUNT_STATES = ("DRAFT", "ACTIVE", "PAUSED", "ARCHIVED")
CHARACTER_STATES = ("DRAFT", "ACTIVE", "ARCHIVED")
WORLD_STATES = ("DRAFT", "ACTIVE", "ARCHIVED")
SERIES_STATES = ("DRAFT", "ACTIVE", "PAUSED", "COMPLETED", "ARCHIVED")
CONTENT_STATES = (
    "IDEA",
    "BRIEFED",
    "GENERATING",
    "GENERATED",
    "QA_PASSED",
    "DRAFT",
    "APPROVED",
    "READY_TO_PUBLISH",
    "PUBLISHED",
    "FAILED",
    "ARCHIVED",
)
MEMORY_KINDS = (
    "account",
    "character",
    "world",
    "series",
    "episode",
    "performance",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    objective: str
    audience: str = ""
    start_at: str | None = None
    end_at: str | None = None
    strategy_id: str | None = None
    success_metrics: tuple[str, ...] = ()
    status: str = "draft"
    account_id: str | None = None
    platform: str = ""
    parent_campaign_id: str | None = None
    series_id: str | None = None
    world_id: str | None = None

    @property
    def id(self) -> str:
        return self.campaign_id

    @property
    def is_global(self) -> bool:
        return not self.platform


@dataclass(frozen=True)
class ContentPackage:
    package_id: str
    title: str
    body: str
    content_type: str = "post"
    evidence_ids: tuple[str, ...] = ()
    brand_id: str | None = None
    creator_id: str | None = None
    campaign_id: str | None = None
    topic: str = ""
    content_pillar: str = ""
    hook: str = ""
    format: str = "post"
    audience: str = ""
    caption: str = ""
    media_assets: tuple[str, ...] = ()
    commerce_intent: str = "none"
    variants: tuple[str, ...] = ()
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    account_id: str | None = None
    series_id: str | None = None
    episode_id: str | None = None
    platform: str = ""
    status: str = "DRAFT"
    character_id: str | None = None
    world_id: str | None = None
    creative_context_id: str | None = None
    revision: int = 1

    @property
    def id(self) -> str:
        return self.package_id


@dataclass(frozen=True)
class PlatformAccount:
    account_id: str
    platform: str
    external_account_id: str = ""
    display_name: str = ""
    status: str = "DRAFT"
    credential_ref: str = ""
    character_id: str | None = None
    world_id: str | None = None
    default_style_profile_id: str | None = None
    social_account_id: str | None = None
    activated_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.platform not in ACCOUNT_PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if self.status not in PLATFORM_ACCOUNT_STATES:
            raise ValueError(f"invalid platform account status: {self.status}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.account_id

    def label(self) -> str:
        return f"{self.platform} / {self.display_name or self.account_id}"


@dataclass(frozen=True)
class VirtualCharacter:
    character_id: str
    account_id: str
    name: str
    gender: str = ""
    age_range: str = ""
    appearance_profile: dict[str, Any] = field(default_factory=dict)
    body_profile: dict[str, Any] = field(default_factory=dict)
    face_profile: dict[str, Any] = field(default_factory=dict)
    hair_profile: dict[str, Any] = field(default_factory=dict)
    skin_profile: dict[str, Any] = field(default_factory=dict)
    clothing_profile: dict[str, Any] = field(default_factory=dict)
    personality_profile: dict[str, Any] = field(default_factory=dict)
    background_story: str = ""
    speaking_style: str = ""
    behavioral_traits: tuple[str, ...] = ()
    visual_identity_rules: dict[str, Any] = field(default_factory=dict)
    forbidden_changes: tuple[str, ...] = ()
    reference_asset_ids: tuple[str, ...] = ()
    status: str = "ACTIVE"
    version: int = 1
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.status not in CHARACTER_STATES:
            raise ValueError(f"invalid character status: {self.status}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.character_id


@dataclass(frozen=True)
class AccountWorld:
    world_id: str
    account_id: str
    name: str
    world_description: str = ""
    core_theme: str = ""
    values: tuple[str, ...] = ()
    tone: str = ""
    visual_language: dict[str, Any] = field(default_factory=dict)
    locations: tuple[str, ...] = ()
    daily_life_rules: tuple[str, ...] = ()
    story_rules: tuple[str, ...] = ()
    audience: str = ""
    taboos: tuple[str, ...] = ()
    brand_rules: tuple[str, ...] = ()
    status: str = "ACTIVE"
    version: int = 1
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.status not in WORLD_STATES:
            raise ValueError(f"invalid world status: {self.status}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.world_id


@dataclass(frozen=True)
class ContentSeries:
    series_id: str
    account_id: str
    world_id: str | None = None
    name: str = ""
    description: str = ""
    series_type: str = "serial"
    content_rules: dict[str, Any] = field(default_factory=dict)
    continuity_rules: dict[str, Any] = field(default_factory=dict)
    status: str = "ACTIVE"
    start_date: str | None = None
    end_date: str | None = None
    current_episode_no: int = 0
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.status not in SERIES_STATES:
            raise ValueError(f"invalid series status: {self.status}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.series_id


@dataclass(frozen=True)
class Episode:
    episode_id: str
    series_id: str
    episode_no: int
    title: str = ""
    brief: str = ""
    previous_episode_id: str | None = None
    next_episode_id: str | None = None
    continuity_context: dict[str, Any] = field(default_factory=dict)
    character_state: dict[str, Any] = field(default_factory=dict)
    world_state: dict[str, Any] = field(default_factory=dict)
    location_state: dict[str, Any] = field(default_factory=dict)
    visual_state: dict[str, Any] = field(default_factory=dict)
    story_state: dict[str, Any] = field(default_factory=dict)
    content_status: str = "IDEA"
    account_id: str = ""
    campaign_id: str | None = None
    content_package_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.content_status not in CONTENT_STATES:
            raise ValueError(f"invalid content status: {self.content_status}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.episode_id


@dataclass(frozen=True)
class CreativeContext:
    context_id: str
    account_id: str
    platform: str
    character_id: str | None = None
    world_id: str | None = None
    series_id: str | None = None
    episode_id: str | None = None
    campaign_id: str | None = None
    user_request: str = ""
    creative_request: str = ""
    normalized_prompt: str = ""
    system_constraints: dict[str, Any] = field(default_factory=dict)
    character_context: dict[str, Any] = field(default_factory=dict)
    world_context: dict[str, Any] = field(default_factory=dict)
    continuity_context: dict[str, Any] = field(default_factory=dict)
    platform_context: dict[str, Any] = field(default_factory=dict)
    generation_parameters: dict[str, Any] = field(default_factory=dict)
    provider: str = ""
    model: str = ""
    provider_task_id: str = ""
    resolved_target: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.context_id


@dataclass(frozen=True)
class ContentRevision:
    revision_id: str
    content_package_id: str
    version: int
    parent_revision_id: str | None = None
    change_summary: str = ""
    snapshot: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    created_by: str = "meiti"

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.revision_id


@dataclass(frozen=True)
class ContinuityMemory:
    memory_id: str
    kind: str
    account_id: str
    subject_id: str
    key: str
    value: Any
    source: str = "continuity"
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in MEMORY_KINDS:
            raise ValueError(f"invalid memory kind: {self.kind}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.memory_id


@dataclass(frozen=True)
class PerformanceFeedback:
    feedback_id: str
    account_id: str
    platform: str
    content_package_id: str = ""
    episode_id: str | None = None
    topic: str = ""
    hook: str = ""
    visual_style: str = ""
    caption_style: str = ""
    duration: float | None = None
    scene: str = ""
    action: str = ""
    audio: str = ""
    engagement: dict[str, Any] = field(default_factory=dict)
    retention: dict[str, Any] = field(default_factory=dict)
    publication_id: str = ""
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.feedback_id


@dataclass(frozen=True)
class AssetLineage:
    lineage_id: str
    asset_id: str
    account_id: str
    series_id: str | None = None
    episode_id: str | None = None
    content_package_id: str | None = None
    creative_context_id: str | None = None
    character_id: str | None = None
    world_id: str | None = None
    user_request: str = ""
    generation_request: dict[str, Any] = field(default_factory=dict)
    provider: str = ""
    provider_task_id: str = ""
    model: str = ""
    attempt_no: int = 1
    parent_asset_id: str | None = None
    qa_decision: str = ""
    published: bool = False
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.lineage_id


@dataclass(frozen=True)
class ResolvedTarget:
    platform: str
    account_id: str
    reason: str
    character_id: str | None = None
    world_id: str | None = None
    series_id: str | None = None
    episode_id: str | None = None
    request: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "account_id": self.account_id,
            "reason": self.reason,
            "character_id": self.character_id,
            "world_id": self.world_id,
            "series_id": self.series_id,
            "episode_id": self.episode_id,
            "request": self.request,
            "extras": dict(self.extras),
        }


class ContinuityError(ValueError):
    """Raised when episode continuity cannot be reconstructed from the database."""


class IsolationError(PermissionError):
    """Raised when a cross-account or cross-platform read is not explicitly allowed."""


def with_status(package: ContentPackage, status: str) -> ContentPackage:
    if status not in CONTENT_STATES:
        raise ValueError(f"invalid content status: {status}")
    return replace(package, status=status, updated_at=utcnow())
