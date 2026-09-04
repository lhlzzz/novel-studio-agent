"""Content owned by Meiti and independent from distribution jobs."""

from __future__ import annotations

import hashlib
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
    "DRAFT",
    "PROMPT_READY",
    "AWAITING_CREATIVE",
    "GENERATING",
    "GENERATED",
    "IMPORTED",
    "QA_PASSED",
    "QA_FAILED",
    "PACKAGE_READY",
    "HANDOFF_READY",
    "READY_TO_PUBLISH",
    "APPROVED",
    "PUBLISHED",
    "ANALYTICS_PENDING",
    "LEARNED",
    "FAILED",
    "REJECTED",
    "ARCHIVED",
)
LIFECYCLE_OWNERS = {
    "DRAFT": "content-agent",
    "PROMPT_READY": "content-agent",
    "AWAITING_CREATIVE": "operator",
    "IMPORTED": "media-agent",
    "QA_PASSED": "media-agent",
    "QA_FAILED": "media-agent",
    "PACKAGE_READY": "content-agent",
    "HANDOFF_READY": "distribution-agent",
    "PUBLISHED": "distribution-agent",
    "ANALYTICS_PENDING": "analytics-agent",
    "LEARNED": "memory-agent",
    "ARCHIVED": "content-agent",
    "REJECTED": "content-agent",
}
MEMORY_KINDS = (
    "account",
    "character",
    "world",
    "series",
    "episode",
    "performance",
)
ASSET_SCOPE_TYPES = (
    "PLATFORM_ACCOUNT",
    "CHARACTER",
    "WORLD",
    "SERIES",
    "EPISODE",
    "GLOBAL",
)
ASSET_ROLES = (
    "CHARACTER_REFERENCE",
    "WORLD_REFERENCE",
    "STYLE_REFERENCE",
    "SCENE_REFERENCE",
    "SOURCE_REFERENCE",
    "GENERATED_PRIMARY",
    "GENERATED_VARIANT",
    "COVER",
    "THUMBNAIL",
    "PUBLISHED",
    "ARCHIVED",
)
ASSET_LIFECYCLES = (
    "DRAFT",
    "IMPORTED",
    "GENERATED",
    "QA_PENDING",
    "QA_PASSED",
    "QA_FAILED",
    "SELECTED",
    "PUBLISHED",
    "ARCHIVED",
    "REJECTED",
)
REUSE_MODES = (
    "NONE",
    "REFERENCE",
    "DERIVED",
    "REUSE",
    "REPUBLISH",
    "REMIX_WITHOUT_NEW_MEDIA",
)
PACKAGE_ASSET_ROLES = ("PRIMARY", "COVER", "THUMBNAIL", "REFERENCE")
LEARNING_SOURCES = ("generated", "published", "analytics", "manual", "research", "review")
GENERATION_MODES = ("MANUAL_CREATIVE_TOOL", "PROVIDER_API", "UNKNOWN")
PROMPT_KINDS = ("IMAGE", "VIDEO", "IMAGE_TO_VIDEO")
PRIMARY_ASSET_ROLES = frozenset({"GENERATED_PRIMARY", "PUBLISHED"})
FRESHNESS_INTENTS = frozenset({"CREATE", "CONTINUE", "GENERATE", "REMIX"})
REUSE_INTENTS = frozenset({"REUSE", "REPUBLISH", "REMIX_WITHOUT_NEW_MEDIA"})


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
    current_revision: str | None = None
    reference_assets: tuple[str, ...] = ()
    primary_assets: tuple[str, ...] = ()
    published_assets: tuple[str, ...] = ()
    prompt_id: str | None = None

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
    derived_from_character_id: str | None = None
    occupation: str = ""
    location: str = ""
    values: tuple[str, ...] = ()
    behavior: str = ""
    speech: str = ""
    style: dict[str, Any] = field(default_factory=dict)
    accessories: tuple[str, ...] = ()
    photography: str = ""
    lighting: str = ""
    platform_personality: str = ""
    content_behavior: str = ""
    audience_relationship: str = ""
    continuity_rules: dict[str, Any] = field(default_factory=dict)
    character_dna: dict[str, Any] = field(default_factory=dict)
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
    city: str = ""
    season: str = ""
    time_of_day: str = ""
    lighting: str = ""
    lifestyle: str = ""
    social_relations: tuple[str, ...] = ()
    world_dna: dict[str, Any] = field(default_factory=dict)
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
    primary_asset_id: str | None = None
    prompt_id: str | None = None
    character_revision: int | None = None
    world_revision: int | None = None
    production_run_id: str | None = None
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
    selected_for_package: bool = False
    source_asset_id: str | None = None
    workflow_id: str | None = None
    reference_asset_ids: tuple[str, ...] = ()
    origin_episode_id: str | None = None
    target_episode_id: str | None = None
    origin_platform: str = ""
    target_platform: str = ""
    reuse_mode: str = "NONE"
    generation_mode: str = ""
    tool: str = ""
    prompt_id: str | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.reuse_mode not in REUSE_MODES:
            raise ValueError(f"invalid reuse_mode: {self.reuse_mode}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.target_episode_id:
            object.__setattr__(self, "target_episode_id", self.episode_id)
        if not self.origin_episode_id:
            object.__setattr__(self, "origin_episode_id", self.episode_id)

    @property
    def id(self) -> str:
        return self.lineage_id


@dataclass(frozen=True)
class AccountContext:
    account_id: str
    platform: str
    account_name: str = ""
    character_id: str | None = None
    world_id: str | None = None
    series_id: str | None = None
    episode_id: str | None = None
    creative_context_id: str | None = None
    campaign_id: str | None = None
    selection_reason: str = "explicit_account"
    resolution_source: str = "explicit_account"
    intent: str = "GENERATE"

    def as_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "platform": self.platform,
            "account_name": self.account_name,
            "character_id": self.character_id,
            "world_id": self.world_id,
            "series_id": self.series_id,
            "episode_id": self.episode_id,
            "creative_context_id": self.creative_context_id,
            "campaign_id": self.campaign_id,
            "selection_reason": self.selection_reason,
            "resolution_source": self.resolution_source,
            "intent": self.intent,
        }


@dataclass(frozen=True)
class ContinuityContext:
    previous_episode_id: str | None = None
    previous_episode_no: int | None = None
    current_episode_id: str | None = None
    current_episode_no: int | None = None
    next_episode_id: str | None = None
    character_continuity: dict[str, Any] = field(default_factory=dict)
    world_continuity: dict[str, Any] = field(default_factory=dict)
    series_continuity: dict[str, Any] = field(default_factory=dict)
    narrative_continuity: dict[str, Any] = field(default_factory=dict)
    knowledge: tuple[Any, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "previous_episode_id": self.previous_episode_id,
            "previous_episode_no": self.previous_episode_no,
            "current_episode_id": self.current_episode_id,
            "current_episode_no": self.current_episode_no,
            "next_episode_id": self.next_episode_id,
            "character_continuity": dict(self.character_continuity),
            "world_continuity": dict(self.world_continuity),
            "series_continuity": dict(self.series_continuity),
            "narrative_continuity": dict(self.narrative_continuity),
            "knowledge": list(self.knowledge),
        }


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


class AmbiguousTarget(IsolationError):
    """Raised when more than one account or series matches and guessing is forbidden."""


class EpisodeConflict(ContinuityError):
    """Raised when concurrent episode or attempt allocation collides."""


class AssetFreshnessError(ContinuityError):
    """Raised when a candidate primary asset is stale or reused without intent."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class MemoryWritebackError(ContinuityError):
    """Raised when MemoryService / Obsidian writeback fails on a production path."""

    def __init__(self, code: str = "MEMORY_WRITEBACK_FAILED", message: str = "MEMORY_WRITEBACK_FAILED") -> None:
        super().__init__(message)
        self.code = code


class ConfigurationBlocked(ContinuityError):
    """Raised when a production account is missing character, world, DNA, pool, or learning."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ExistingAssetError(AssetFreshnessError):
    """Raised when an imported file already exists as an immutable asset."""


class CrossPlatformAssetReuse(IsolationError):
    """Raised when a primary asset is reused across platforms."""


@dataclass(frozen=True)
class PlatformAssetPool:
    pool_id: str
    account_id: str
    platform: str
    character_id: str | None = None
    world_id: str | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.platform not in ACCOUNT_PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.pool_id


@dataclass(frozen=True)
class PlatformCreativeDNA:
    dna_id: str
    account_id: str
    platform: str
    visual_style: dict[str, Any] = field(default_factory=dict)
    copy_style: dict[str, Any] = field(default_factory=dict)
    hook_style: str = ""
    camera_style: str = ""
    motion_style: str = ""
    emotion_style: str = ""
    audience_relationship: str = ""
    cta_style: str = ""
    content_frequency: str = ""
    asset_freshness_policy: str = "NEW_PRIMARY_ASSET_REQUIRED"
    prompt_dna: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.platform not in ACCOUNT_PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.dna_id


@dataclass(frozen=True)
class PromptPackage:
    prompt_id: str
    account_id: str
    platform: str
    kind: str = "IMAGE"
    character_id: str | None = None
    world_id: str | None = None
    series_id: str | None = None
    episode_id: str | None = None
    character_lock: str = ""
    world_lock: str = ""
    scene_prompt: str = ""
    visual_style: str = ""
    camera: str = ""
    motion: str = ""
    composition: str = ""
    lighting: str = ""
    negative_prompt: str = ""
    lens: str = ""
    material_texture: str = ""
    authenticity: str = ""
    shot_list: tuple[str, ...] = ()
    temporal_sequence: str = ""
    camera_movement: str = ""
    character_motion: str = ""
    environment_motion: str = ""
    start_state: str = ""
    end_state: str = ""
    duration: str = ""
    aspect_ratio: str = ""
    copy_ready: str = ""
    reference_assets: tuple[str, ...] = ()
    source_assets: tuple[str, ...] = ()
    source_asset_id: str | None = None
    recommended_model: str = ""
    recommended_size: str = ""
    recommended_ratio: str = ""
    recommended_duration: str = ""
    learning_basis: tuple[str, ...] = ()
    prompt_patterns: tuple[str, ...] = ()
    lechuang_parameters: dict[str, Any] = field(default_factory=dict)
    prompt_hash: str = ""
    version: int = 1
    parent_prompt_id: str | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in PROMPT_KINDS:
            raise ValueError(f"invalid prompt kind: {self.kind}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.prompt_hash and self.copy_ready:
            object.__setattr__(self, "prompt_hash", hashlib.sha256(self.copy_ready.encode("utf-8")).hexdigest())

    @property
    def id(self) -> str:
        return self.prompt_id


@dataclass(frozen=True)
class PromptPattern:
    pattern_id: str
    platform: str
    account_id: str | None = None
    category: str = ""
    prompt_fragment: str = ""
    positive_count: int = 0
    negative_count: int = 0
    confidence: float = 0.0
    source_episode_ids: tuple[str, ...] = ()
    global_pattern: bool = False
    promotion_status: str = "PLATFORM"
    sample_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not self.global_pattern and self.platform not in ACCOUNT_PLATFORMS and self.platform != "GLOBAL":
            raise ValueError(f"unsupported platform: {self.platform}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.pattern_id


@dataclass(frozen=True)
class PlatformLearningProfile:
    profile_id: str
    account_id: str
    platform: str
    successful_patterns: tuple[str, ...] = ()
    failed_patterns: tuple[str, ...] = ()
    high_performance_topics: tuple[str, ...] = ()
    high_performance_hooks: tuple[str, ...] = ()
    high_performance_visuals: tuple[str, ...] = ()
    audience_preferences: tuple[str, ...] = ()
    avoid_patterns: tuple[str, ...] = ()
    prompt_patterns: tuple[str, ...] = ()
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.platform not in ACCOUNT_PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.profile_id


@dataclass(frozen=True)
class ContentPackageAsset:
    mapping_id: str
    package_id: str
    asset_id: str
    role: str = "PRIMARY"
    selected: bool = False
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.role not in PACKAGE_ASSET_ROLES:
            raise ValueError(f"invalid package asset role: {self.role}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.mapping_id


def with_status(package: ContentPackage, status: str) -> ContentPackage:
    if status not in CONTENT_STATES:
        raise ValueError(f"invalid content status: {status}")
    return replace(package, status=status, updated_at=utcnow())


PATTERN_PROMOTION_STATES = ("PLATFORM", "GLOBAL_CANDIDATE", "GLOBAL_PATTERN", "REJECTED")
PRODUCTION_RUN_STATES = ("OPEN", "AWAITING_CREATIVE", "IMPORTED", "PACKAGED", "HANDED_OFF", "LEARNED", "CLOSED", "BLOCKED")
EVIDENCE_SOURCES = ("code", "operator", "lechuang", "analytics", "memory", "audit")


@dataclass(frozen=True)
class ProductionRun:
    run_id: str
    account_id: str
    platform: str
    episode_id: str | None = None
    prompt_id: str | None = None
    asset_id: str | None = None
    package_id: str | None = None
    handoff_id: str | None = None
    publication_id: str | None = None
    analytics_id: str | None = None
    learning_id: str | None = None
    status: str = "OPEN"
    request: str = ""
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.status not in PRODUCTION_RUN_STATES:
            raise ValueError(f"invalid production run status: {self.status}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.run_id


@dataclass(frozen=True)
class ProductionEvidence:
    evidence_id: str
    kind: str
    account_id: str
    platform: str
    status: str = "PASS"
    episode_id: str | None = None
    prompt_id: str | None = None
    asset_id: str | None = None
    package_id: str | None = None
    handoff_id: str | None = None
    publication_id: str | None = None
    analytics_id: str | None = None
    learning_id: str | None = None
    production_run_id: str | None = None
    source: str = "operator"
    detail: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.source not in EVIDENCE_SOURCES:
            raise ValueError(f"invalid evidence source: {self.source}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.evidence_id


@dataclass(frozen=True)
class AnalyticsRecord:
    analytics_id: str
    account_id: str
    platform: str
    episode_id: str | None = None
    package_id: str | None = None
    handoff_id: str | None = None
    publication_id: str | None = None
    impressions: int | None = None
    likes: int | None = None
    favorites: int | None = None
    comments: int | None = None
    shares: int | None = None
    followers_gained: int | None = None
    published_at: str | None = None
    topic: str = ""
    cover: str = ""
    prompt_pattern: str = ""
    source: str = "manual"
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.analytics_id


@dataclass(frozen=True)
class LearningRecord:
    learning_id: str
    account_id: str
    platform: str
    episode_id: str | None = None
    analytics_id: str | None = None
    pattern_ids: tuple[str, ...] = ()
    what_worked: str = ""
    what_failed: str = ""
    visual_learning: str = ""
    content_learning: str = ""
    prompt_learning: str = ""
    audience_learning: str = ""
    next_recommendation: str = ""
    reason: str = ""
    source_episode_ids: tuple[str, ...] = ()
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.learning_id


@dataclass(frozen=True)
class CreativeExecutionReceipt:
    receipt_id: str
    asset_id: str
    prompt_id: str | None = None
    tool: str = "lechuang"
    model: str = "UNKNOWN"
    generated_at: str | None = None
    operator: str = "operator"
    source_asset_id: str | None = None
    generation_mode: str = "MANUAL_CREATIVE_TOOL"
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not self.model:
            object.__setattr__(self, "model", "UNKNOWN")
        if not self.generated_at:
            object.__setattr__(self, "generated_at", utcnow())
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.receipt_id


@dataclass(frozen=True)
class CharacterRevision:
    revision_id: str
    character_id: str
    account_id: str
    version: int
    snapshot: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.revision_id


@dataclass(frozen=True)
class WorldRevision:
    revision_id: str
    world_id: str
    account_id: str
    version: int
    snapshot: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.revision_id


@dataclass(frozen=True)
class AssetReferenceSnapshot:
    snapshot_id: str
    prompt_id: str
    asset_id: str
    role: str = "SCENE_REFERENCE"
    reason: str = ""
    prompt_influence: str = ""
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.snapshot_id


@dataclass(frozen=True)
class PatternPromotion:
    promotion_id: str
    pattern_id: str
    platform: str
    status: str = "PLATFORM"
    sample_count: int = 0
    cross_platform_evidence: tuple[str, ...] = ()
    confidence: float = 0.0
    reason: str = ""
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.status not in PATTERN_PROMOTION_STATES:
            raise ValueError(f"invalid pattern promotion status: {self.status}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.promotion_id


@dataclass(frozen=True)
class LifecycleTransition:
    transition_id: str
    episode_id: str
    account_id: str
    from_status: str
    to_status: str
    owner: str
    evidence_id: str | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.transition_id
