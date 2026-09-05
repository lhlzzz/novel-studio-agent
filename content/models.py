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

PLATFORM_ACCOUNT_STATES = ("DRAFT", "ACTIVE", "PAUSED", "DISABLED", "ARCHIVED")
CONNECTION_STATES = (
    "NOT_CONNECTED",
    "CONNECTING",
    "CONNECTED",
    "VERIFIED",
    "DEGRADED",
    "EXPIRED",
    "REVOKED",
    "BLOCKED",
)
STRATEGY_STATES = ("DRAFT", "ACTIVE", "SUPERSEDED", "ARCHIVED")
MEMORY_LIFECYCLE_STATES = ("CURRENT", "HISTORICAL", "SUPERSEDED", "EXPIRED", "PENDING", "VERIFIED")
NOVELTY_VERDICTS = ("NOVEL", "LOW_NOVELTY", "SATURATED", "DUPLICATE")
SATURATION_ACTIONS = ("avoid", "reduce", "continue", "increase")
IDEA_DECISIONS = ("ACCEPT", "MODIFY", "REJECT")
KNOWLEDGE_CERTAINTY = ("UNKNOWN", "KNOWN", "INFERRED", "RECOMMENDED", "CONFIRMED")
KNOWLEDGE_PRECEDENCE = (
    "USER_OVERRIDE",
    "USER_DEFINED",
    "VERIFIED_LEARNING",
    "SYSTEM_DERIVED",
    "SYSTEM_RECOMMENDED",
    "DEFAULT",
    "UNKNOWN",
)
CREATOR_KNOWLEDGE_FIELDS = (
    "account_subject",
    "account_type",
    "account_category",
    "description",
    "positioning",
    "core_promise",
    "differentiation",
    "target_audience",
    "audience_profile",
    "audience_age_range",
    "audience_gender",
    "audience_location",
    "audience_interests",
    "content_pillars",
    "content_direction",
    "growth_objective",
    "commercial_direction",
    "persona",
    "personality",
    "values",
    "tone",
    "speaking_style",
    "behavior",
    "emotional_style",
    "audience_relationship",
    "taboos",
    "visual_identity",
    "visual_language",
    "color_system",
    "photography_style",
    "camera_style",
    "lighting_style",
    "composition_style",
    "clothing_style",
    "environment_style",
    "retouching_policy",
    "visual_forbidden_rules",
    "title_rules",
    "hook_rules",
    "caption_rules",
    "body_rules",
    "image_rules",
    "video_rules",
    "hashtag_rules",
    "topic_rules",
    "forbidden_topics",
    "forbidden_phrases",
    "posting_frequency",
    "preferred_publish_windows",
    "content_mix",
    "content_ratio",
    "series_strategy",
    "continuity_strategy",
    "platform_strategy",
    "quality_bar",
)
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
KNOWLEDGE_SOURCES = (
    "USER_OVERRIDE",
    "USER_DEFINED",
    "VERIFIED_LEARNING",
    "SYSTEM_DERIVED",
    "SYSTEM_RECOMMENDED",
    "DEFAULT",
    "LEARNED",
    "TEMPORARY",
    "UNKNOWN",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class KnowledgeField:
    value: Any = None
    source: str = "UNKNOWN"
    reason: str = ""
    changed_by: str = ""
    changed_at: str | None = None
    certainty: str = ""

    def __post_init__(self) -> None:
        if self.source not in KNOWLEDGE_SOURCES:
            raise ValueError(f"invalid knowledge source: {self.source}")
        if self.certainty and self.certainty not in KNOWLEDGE_CERTAINTY:
            raise ValueError(f"invalid knowledge certainty: {self.certainty}")
        if not self.certainty:
            if self.source in {"UNKNOWN"} or self.value in (None, "", (), []):
                object.__setattr__(self, "certainty", "UNKNOWN")
            elif self.source in {"USER_OVERRIDE", "USER_DEFINED"}:
                object.__setattr__(self, "certainty", "CONFIRMED")
            elif self.source in {"VERIFIED_LEARNING", "LEARNED"}:
                object.__setattr__(self, "certainty", "KNOWN")
            elif self.source in {"SYSTEM_DERIVED"}:
                object.__setattr__(self, "certainty", "INFERRED")
            elif self.source in {"SYSTEM_RECOMMENDED", "DEFAULT"}:
                object.__setattr__(self, "certainty", "RECOMMENDED")
            else:
                object.__setattr__(self, "certainty", "UNKNOWN")
        if not self.changed_at and self.value not in (None, "", (), []):
            object.__setattr__(self, "changed_at", utcnow())

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source,
            "reason": self.reason,
            "changed_by": self.changed_by,
            "changed_at": self.changed_at,
            "certainty": self.certainty,
        }

    def known(self) -> bool:
        return self.certainty not in {"UNKNOWN", "RECOMMENDED"} and self.value not in (None, "", (), [])


def knowledge_field(
    value: Any = None,
    *,
    source: str = "UNKNOWN",
    reason: str = "",
    changed_by: str = "",
    changed_at: str | None = None,
    certainty: str = "",
) -> KnowledgeField:
    if isinstance(value, KnowledgeField):
        return value
    return KnowledgeField(
        value=value,
        source=source,
        reason=reason,
        changed_by=changed_by,
        changed_at=changed_at,
        certainty=certainty,
    )


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
    content_decision_id: str | None = None

    @property
    def id(self) -> str:
        return self.package_id


def _coerce_knowledge(value: Any, *, default_source: str = "UNKNOWN") -> "KnowledgeField":
    if isinstance(value, KnowledgeField):
        return value
    if isinstance(value, dict) and ("source" in value or "value" in value):
        return KnowledgeField(
            value=value.get("value"),
            source=value.get("source") or default_source,
            reason=value.get("reason") or "",
            changed_by=value.get("changed_by") or "",
            changed_at=value.get("changed_at"),
            certainty=value.get("certainty") or "",
        )
    if value in (None, "", (), []):
        return KnowledgeField(value=None, source="UNKNOWN")
    return KnowledgeField(value=value, source=default_source)


@dataclass(frozen=True)
class PlatformAccount:
    """Canonical Creator Identity. Table remains platform_accounts for FK stability.

    credential_ref / social_account_id / external_account_id are optional connection
    pointers. They never decide whether this Creator is READY.
    """

    account_id: str
    platform: str
    external_account_id: str = ""
    display_name: str = ""
    account_name: str = ""
    status: str = "DRAFT"
    credential_ref: str = ""
    character_id: str | None = None
    world_id: str | None = None
    series_id: str | None = None
    default_style_profile_id: str | None = None
    social_account_id: str | None = None
    activated_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    account_subject: KnowledgeField = field(default_factory=KnowledgeField)
    account_type: KnowledgeField = field(default_factory=KnowledgeField)
    account_category: KnowledgeField = field(default_factory=KnowledgeField)
    description: KnowledgeField = field(default_factory=KnowledgeField)
    positioning: KnowledgeField = field(default_factory=KnowledgeField)
    core_promise: KnowledgeField = field(default_factory=KnowledgeField)
    differentiation: KnowledgeField = field(default_factory=KnowledgeField)
    target_audience: KnowledgeField = field(default_factory=KnowledgeField)
    audience_profile: KnowledgeField = field(default_factory=KnowledgeField)
    audience_age_range: KnowledgeField = field(default_factory=KnowledgeField)
    audience_gender: KnowledgeField = field(default_factory=KnowledgeField)
    audience_location: KnowledgeField = field(default_factory=KnowledgeField)
    audience_interests: KnowledgeField = field(default_factory=KnowledgeField)
    content_pillars: KnowledgeField = field(default_factory=KnowledgeField)
    content_direction: KnowledgeField = field(default_factory=KnowledgeField)
    growth_objective: KnowledgeField = field(default_factory=KnowledgeField)
    commercial_direction: KnowledgeField = field(default_factory=KnowledgeField)
    persona: KnowledgeField = field(default_factory=KnowledgeField)
    personality: KnowledgeField = field(default_factory=KnowledgeField)
    values: KnowledgeField = field(default_factory=KnowledgeField)
    tone: KnowledgeField = field(default_factory=KnowledgeField)
    speaking_style: KnowledgeField = field(default_factory=KnowledgeField)
    behavior: KnowledgeField = field(default_factory=KnowledgeField)
    emotional_style: KnowledgeField = field(default_factory=KnowledgeField)
    audience_relationship: KnowledgeField = field(default_factory=KnowledgeField)
    taboos: KnowledgeField = field(default_factory=KnowledgeField)
    visual_identity: KnowledgeField = field(default_factory=KnowledgeField)
    visual_language: KnowledgeField = field(default_factory=KnowledgeField)
    color_system: KnowledgeField = field(default_factory=KnowledgeField)
    photography_style: KnowledgeField = field(default_factory=KnowledgeField)
    camera_style: KnowledgeField = field(default_factory=KnowledgeField)
    lighting_style: KnowledgeField = field(default_factory=KnowledgeField)
    composition_style: KnowledgeField = field(default_factory=KnowledgeField)
    clothing_style: KnowledgeField = field(default_factory=KnowledgeField)
    environment_style: KnowledgeField = field(default_factory=KnowledgeField)
    retouching_policy: KnowledgeField = field(default_factory=KnowledgeField)
    visual_forbidden_rules: KnowledgeField = field(default_factory=KnowledgeField)
    title_rules: KnowledgeField = field(default_factory=KnowledgeField)
    hook_rules: KnowledgeField = field(default_factory=KnowledgeField)
    caption_rules: KnowledgeField = field(default_factory=KnowledgeField)
    body_rules: KnowledgeField = field(default_factory=KnowledgeField)
    image_rules: KnowledgeField = field(default_factory=KnowledgeField)
    video_rules: KnowledgeField = field(default_factory=KnowledgeField)
    hashtag_rules: KnowledgeField = field(default_factory=KnowledgeField)
    topic_rules: KnowledgeField = field(default_factory=KnowledgeField)
    forbidden_topics: KnowledgeField = field(default_factory=KnowledgeField)
    forbidden_phrases: KnowledgeField = field(default_factory=KnowledgeField)
    posting_frequency: KnowledgeField = field(default_factory=KnowledgeField)
    preferred_publish_windows: KnowledgeField = field(default_factory=KnowledgeField)
    content_mix: KnowledgeField = field(default_factory=KnowledgeField)
    content_ratio: KnowledgeField = field(default_factory=KnowledgeField)
    series_strategy: KnowledgeField = field(default_factory=KnowledgeField)
    continuity_strategy: KnowledgeField = field(default_factory=KnowledgeField)
    platform_strategy: KnowledgeField = field(default_factory=KnowledgeField)
    quality_bar: KnowledgeField = field(default_factory=KnowledgeField)
    current_strategy_id: str | None = None
    current_strategy_version: int | None = None
    current_episode_id: str | None = None
    current_phase: str = ""
    current_objective: str = ""
    current_next_action: str = ""
    identity_payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.platform not in ACCOUNT_PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if self.status not in PLATFORM_ACCOUNT_STATES:
            raise ValueError(f"invalid platform account status: {self.status}")
        if not self.account_name:
            object.__setattr__(self, "account_name", self.display_name or self.account_id)
        for name in CREATOR_KNOWLEDGE_FIELDS:
            object.__setattr__(self, name, _coerce_knowledge(getattr(self, name)))
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.account_id

    @property
    def current_character_id(self) -> str | None:
        return self.character_id

    @property
    def current_world_id(self) -> str | None:
        return self.world_id

    @property
    def current_series_id(self) -> str | None:
        return self.series_id

    def label(self) -> str:
        return f"{self.platform} / {self.display_name or self.account_name or self.account_id}"

    def field_value(self, name: str) -> Any:
        field_obj = getattr(self, name)
        if isinstance(field_obj, KnowledgeField):
            return field_obj.value
        return field_obj

    def known(self, name: str) -> bool:
        field_obj = getattr(self, name)
        if isinstance(field_obj, KnowledgeField):
            return field_obj.source not in {"UNKNOWN", "DEFAULT"} and field_obj.value not in (None, "", (), [])
        return bool(field_obj)

    def as_dict(self) -> dict[str, Any]:
        payload = dict(self.__dict__)
        for name in CREATOR_KNOWLEDGE_FIELDS:
            value = getattr(self, name)
            payload[name] = value.as_dict() if isinstance(value, KnowledgeField) else value
        return payload


CreatorAccount = PlatformAccount


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
    series_goal: str = ""
    series_theme: str = ""
    series_arc: str = ""
    current_phase: str = ""
    phase_goal: str = ""
    next_direction_candidates: tuple[str, ...] = ()
    completion_condition: str = ""
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
    strategy_id: str | None = None
    strategy_version: int | None = None
    creator_state_id: str | None = None
    content_decision_id: str | None = None
    creator_state_snapshot: dict[str, Any] = field(default_factory=dict)
    novelty_snapshot: dict[str, Any] = field(default_factory=dict)
    portfolio_snapshot: dict[str, Any] = field(default_factory=dict)
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

    def __init__(self, message: str, code: str = "ISOLATION_ERROR") -> None:
        super().__init__(message)
        self.code = code


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

    def __init__(self, code: str = "CROSS_PLATFORM_ASSET_REUSE", message: str | None = None) -> None:
        super().__init__(message or code, code=code)


class CalendarSlotConflict(ConfigurationBlocked):
    """Raised when a calendar slot already has a canonical entry."""

    def __init__(self, message: str = "CALENDAR_SLOT_CONFLICT") -> None:
        super().__init__("CALENDAR_SLOT_CONFLICT", message)


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
    strategy_basis: tuple[str, ...] = ()
    decision_basis: tuple[str, ...] = ()
    novelty_basis: tuple[str, ...] = ()
    continuity_basis: tuple[str, ...] = ()
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
PRODUCTION_RUN_STATES = (
    "CREATED",
    "PROMPT_READY",
    "CREATIVE_EXECUTION",
    "ASSET_IMPORTED",
    "QA_PASSED",
    "PACKAGE_READY",
    "HANDED_OFF",
    "PUBLISHED",
    "ANALYTICS_CAPTURED",
    "LEARNING_VERIFIED",
    "CLOSED",
    "BLOCKED",
    "OPEN",
    "AWAITING_CREATIVE",
    "IMPORTED",
    "PACKAGED",
    "LEARNED",
)
ANALYTICS_ORIGINS = ("MANUAL", "PROVIDER")
ANALYTICS_VERIFICATION_STATES = ("VERIFIED", "UNVERIFIED")
PROJECTION_STATES = ("COMMITTED", "PROJECTION_PENDING", "PROJECTED")
EVIDENCE_SOURCES = ("code", "operator", "lechuang", "analytics", "memory", "audit")
TASK_TYPES = (
    "ACCOUNT_SETUP",
    "ACCOUNT_MAINTENANCE",
    "CONTENT_IDEA",
    "CONTENT_PLAN",
    "PROMPT_GENERATION",
    "CREATIVE_EXECUTION",
    "ASSET_IMPORT",
    "QA",
    "PACKAGE",
    "HANDOFF",
    "PUBLISH",
    "ANALYTICS",
    "LEARNING",
    "RESEARCH",
    "REVIEW",
)
TASK_STATES = (
    "TODO",
    "READY",
    "IN_PROGRESS",
    "WAITING_OPERATOR",
    "WAITING_EXTERNAL",
    "BLOCKED",
    "DONE",
    "CANCELLED",
)
ALLOWED_TASK_TRANSITIONS = {
    "TODO": frozenset({"READY", "CANCELLED"}),
    "READY": frozenset({"IN_PROGRESS", "BLOCKED", "CANCELLED"}),
    "IN_PROGRESS": frozenset({"WAITING_OPERATOR", "WAITING_EXTERNAL", "BLOCKED", "DONE"}),
    "WAITING_OPERATOR": frozenset({"IN_PROGRESS"}),
    "WAITING_EXTERNAL": frozenset({"IN_PROGRESS"}),
    "BLOCKED": frozenset({"READY"}),
    "DONE": frozenset(),
    "CANCELLED": frozenset(),
}
TASK_TRANSITION_PATHS = {
    ("TODO", "READY"): ("READY",),
    ("TODO", "IN_PROGRESS"): ("READY", "IN_PROGRESS"),
    ("TODO", "WAITING_OPERATOR"): ("READY", "IN_PROGRESS", "WAITING_OPERATOR"),
    ("TODO", "DONE"): ("READY", "IN_PROGRESS", "DONE"),
    ("TODO", "CANCELLED"): ("CANCELLED",),
    ("READY", "IN_PROGRESS"): ("IN_PROGRESS",),
    ("READY", "WAITING_OPERATOR"): ("IN_PROGRESS", "WAITING_OPERATOR"),
    ("READY", "DONE"): ("IN_PROGRESS", "DONE"),
    ("READY", "BLOCKED"): ("BLOCKED",),
    ("READY", "CANCELLED"): ("CANCELLED",),
    ("IN_PROGRESS", "WAITING_OPERATOR"): ("WAITING_OPERATOR",),
    ("IN_PROGRESS", "WAITING_EXTERNAL"): ("WAITING_EXTERNAL",),
    ("IN_PROGRESS", "BLOCKED"): ("BLOCKED",),
    ("IN_PROGRESS", "DONE"): ("DONE",),
    ("WAITING_OPERATOR", "IN_PROGRESS"): ("IN_PROGRESS",),
    ("WAITING_OPERATOR", "DONE"): ("IN_PROGRESS", "DONE"),
    ("WAITING_EXTERNAL", "IN_PROGRESS"): ("IN_PROGRESS",),
    ("WAITING_EXTERNAL", "DONE"): ("IN_PROGRESS", "DONE"),
    ("BLOCKED", "READY"): ("READY",),
}
TASK_PRIORITIES = ("CRITICAL", "HIGH", "NORMAL", "LOW")
PRODUCTION_CHAIN = (
    "CONTENT_PLAN",
    "PROMPT_GENERATION",
    "CREATIVE_EXECUTION",
    "ASSET_IMPORT",
    "QA",
    "PACKAGE",
    "HANDOFF",
    "ANALYTICS",
    "LEARNING",
)
CALENDAR_STATES = (
    "PLANNED",
    "READY",
    "PRODUCING",
    "READY_TO_PUBLISH",
    "PUBLISHED",
    "MISSED",
    "CANCELLED",
)
READINESS_STATES = ("READY", "PARTIAL", "BLOCKED", "NOT_CONFIGURED", "PASS", "FAIL", "NOT_VERIFIED", "BLOCKED_EXTERNAL", "NEEDS_MORE_EVIDENCE", "UNKNOWN")
LEARNING_EVIDENCE_STATES = (
    "OBSERVATION",
    "PENDING",
    "VERIFIED",
    "REJECTED",
    "SUPERSEDED",
    "NOT_ENOUGH_EVIDENCE",
    "NOT_VERIFIED",
)
CANONICAL_ANALYTICS_STORE = "content.models.AnalyticsRecord"


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
    task_id: str | None = None
    strategy_id: str | None = None
    creator_state_id: str | None = None
    content_decision_id: str | None = None
    status: str = "CREATED"
    request: str = ""
    creative_provider: str = ""
    creative_job_id: str = ""
    creative_model: str = ""
    creative_request_snapshot: dict[str, Any] = field(default_factory=dict)
    creative_result_snapshot: dict[str, Any] = field(default_factory=dict)
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
    clicks: int | None = None
    followers_gained: int | None = None
    followers_delta: int | None = None
    published_at: str | None = None
    observed_at: str | None = None
    topic: str = ""
    cover: str = ""
    prompt_pattern: str = ""
    source: str = "manual"
    origin: str = "MANUAL"
    verification_status: str = "UNVERIFIED"
    provider: str = ""
    provider_payload: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None

    def __post_init__(self) -> None:
        origin = (self.origin or self.source or "MANUAL").upper()
        if origin in {"PROVIDER", "VERIFIED_PROVIDER", "PROVIDER_OBSERVED"}:
            origin = "PROVIDER"
        elif origin in {"MANUAL", "OPERATOR", "MANUAL_OBSERVATION"} or (self.source or "").lower() == "manual":
            origin = "MANUAL"
        if origin not in ANALYTICS_ORIGINS:
            origin = "MANUAL"
        object.__setattr__(self, "origin", origin)
        verification = (self.verification_status or "UNVERIFIED").upper()
        if origin != "PROVIDER":
            verification = "UNVERIFIED"
        if verification not in ANALYTICS_VERIFICATION_STATES:
            verification = "UNVERIFIED"
        if origin == "PROVIDER" and verification == "VERIFIED":
            payload = dict(self.provider_payload or {})
            if not self.publication_id or not payload:
                verification = "UNVERIFIED"
        object.__setattr__(self, "verification_status", verification)
        if self.followers_delta is None and self.followers_gained is not None:
            object.__setattr__(self, "followers_delta", self.followers_gained)
        if self.followers_gained is None and self.followers_delta is not None:
            object.__setattr__(self, "followers_gained", self.followers_delta)
        if not self.observed_at:
            object.__setattr__(self, "observed_at", utcnow())
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
    prompt_id: str | None = None
    asset_id: str | None = None
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
    evidence_status: str = "NOT_VERIFIED"
    learning_status: str = ""
    failure_type: str = ""
    diagnosis: str = ""
    root_cause: str = ""
    evidence_gap: str = ""
    outcome: str = ""
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.evidence_status not in LEARNING_EVIDENCE_STATES:
            raise ValueError(f"invalid learning evidence status: {self.evidence_status}")
        if not self.learning_status:
            object.__setattr__(self, "learning_status", self.evidence_status)
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
    production_run_id: str | None = None
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
    task_id: str | None = None
    reason: str = ""
    operator: str = ""
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.transition_id


@dataclass(frozen=True)
class AccountProfile:
    """Projection of CreatorAccount identity/profile fields. Not an identity owner."""

    account_id: str
    platform: str
    display_name: str = ""
    external_account_id: str = ""
    status: str = "DRAFT"
    character_id: str | None = None
    world_id: str | None = None
    series_id: str | None = None
    account_objective: KnowledgeField = field(default_factory=KnowledgeField)
    target_audience: KnowledgeField = field(default_factory=KnowledgeField)
    positioning: KnowledgeField = field(default_factory=KnowledgeField)
    content_pillars: KnowledgeField = field(default_factory=KnowledgeField)
    brand_voice: KnowledgeField = field(default_factory=KnowledgeField)
    visual_style: KnowledgeField = field(default_factory=KnowledgeField)
    content_frequency: KnowledgeField = field(default_factory=KnowledgeField)
    preferred_publish_windows: KnowledgeField = field(default_factory=KnowledgeField)
    content_formats: KnowledgeField = field(default_factory=KnowledgeField)
    operating_rules: KnowledgeField = field(default_factory=KnowledgeField)
    forbidden_rules: KnowledgeField = field(default_factory=KnowledgeField)
    manual_notes: KnowledgeField = field(default_factory=KnowledgeField)
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.platform not in ACCOUNT_PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        object.__setattr__(self, "account_objective", knowledge_field(self.account_objective))
        object.__setattr__(self, "target_audience", knowledge_field(self.target_audience))
        object.__setattr__(self, "positioning", knowledge_field(self.positioning))
        object.__setattr__(self, "content_pillars", knowledge_field(self.content_pillars))
        object.__setattr__(self, "brand_voice", knowledge_field(self.brand_voice))
        object.__setattr__(self, "visual_style", knowledge_field(self.visual_style))
        object.__setattr__(self, "content_frequency", knowledge_field(self.content_frequency))
        object.__setattr__(self, "preferred_publish_windows", knowledge_field(self.preferred_publish_windows))
        object.__setattr__(self, "content_formats", knowledge_field(self.content_formats))
        object.__setattr__(self, "operating_rules", knowledge_field(self.operating_rules))
        object.__setattr__(self, "forbidden_rules", knowledge_field(self.forbidden_rules))
        object.__setattr__(self, "manual_notes", knowledge_field(self.manual_notes))
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.account_id

    def field_value(self, name: str) -> Any:
        field_obj = getattr(self, name)
        if isinstance(field_obj, KnowledgeField):
            return field_obj.value
        return field_obj

    @classmethod
    def from_account(cls, account: "PlatformAccount") -> "AccountProfile":
        objective = account.growth_objective
        if not account.known("growth_objective") and account.current_objective:
            objective = knowledge_field(account.current_objective, source="SYSTEM_DERIVED")
        return cls(
            account_id=account.account_id,
            platform=account.platform,
            display_name=account.display_name,
            external_account_id=account.external_account_id,
            status=account.status,
            character_id=account.character_id,
            world_id=account.world_id,
            series_id=account.series_id,
            account_objective=objective,
            target_audience=account.target_audience,
            positioning=account.positioning,
            content_pillars=account.content_pillars,
            brand_voice=account.tone if account.known("tone") else account.persona,
            visual_style=account.visual_identity if account.known("visual_identity") else account.visual_language,
            content_frequency=account.posting_frequency,
            preferred_publish_windows=account.preferred_publish_windows,
            content_formats=account.content_mix,
            operating_rules=account.platform_strategy,
            forbidden_rules=account.forbidden_topics if account.known("forbidden_topics") else account.taboos,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )


@dataclass(frozen=True)
class AccountOperatingState:
    account_id: str
    platform: str
    current_objective: str = ""
    current_priority: str = "NORMAL"
    current_series: str | None = None
    current_episode: str | None = None
    current_task: str | None = None
    current_campaign: str | None = None
    current_strategy: str = ""
    current_content_status: str = "IDEA"
    last_published_episode: str | None = None
    last_generated_asset: str | None = None
    last_learning: str | None = None
    learning_summary: str = ""
    next_action: str = ""
    next_due_at: str | None = None
    paused_until: str | None = None
    operator_notes: str = ""
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.platform not in ACCOUNT_PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if self.current_priority not in TASK_PRIORITIES:
            raise ValueError(f"invalid priority: {self.current_priority}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.account_id


@dataclass(frozen=True)
class ManualOverride:
    override_id: str
    account_id: str
    platform: str
    target_kind: str
    target_id: str
    field_name: str
    old_value: Any = None
    new_value: Any = None
    changed_by: str = "operator"
    reason: str = ""
    source: str = "USER_OVERRIDE"
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.source not in KNOWLEDGE_SOURCES:
            raise ValueError(f"invalid override source: {self.source}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.override_id


@dataclass(frozen=True)
class CreatorTask:
    task_id: str
    account_id: str
    platform: str
    task_type: str
    title: str
    description: str = ""
    priority: str = "NORMAL"
    status: str = "TODO"
    due_at: str | None = None
    episode_id: str | None = None
    series_id: str | None = None
    prompt_id: str | None = None
    asset_id: str | None = None
    package_id: str | None = None
    production_run_id: str | None = None
    parent_task_id: str | None = None
    next_task_id: str | None = None
    next_task_type: str | None = None
    dependencies: tuple[str, ...] = ()
    operator_notes: str = ""
    blocked_reason: str = ""
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None

    def __post_init__(self) -> None:
        if self.task_type not in TASK_TYPES:
            raise ValueError(f"invalid task type: {self.task_type}")
        if self.status not in TASK_STATES:
            raise ValueError(f"invalid task status: {self.status}")
        if self.priority not in TASK_PRIORITIES:
            raise ValueError(f"invalid task priority: {self.priority}")
        if self.platform not in ACCOUNT_PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.task_id


@dataclass(frozen=True)
class ContentCalendarEntry:
    calendar_id: str
    account_id: str
    platform: str
    date: str
    slot: str = "default"
    episode_id: str | None = None
    task_id: str | None = None
    status: str = "PLANNED"
    topic: str = ""
    format: str = "image"
    priority: str = "NORMAL"
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.status not in CALENDAR_STATES:
            raise ValueError(f"invalid calendar status: {self.status}")
        if self.priority not in TASK_PRIORITIES:
            raise ValueError(f"invalid calendar priority: {self.priority}")
        if self.platform not in ACCOUNT_PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.calendar_id


@dataclass(frozen=True)
class EpisodeConcept:
    account_id: str
    platform: str
    series_id: str | None
    title: str
    topic: str
    format: str
    brief: str
    reason: str
    freshness: str
    continuity: str
    learning_basis: tuple[str, ...] = ()
    reference_asset_ids: tuple[str, ...] = ()
    prompt_kind: str = "IMAGE"
    recent_topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductionReadinessRecord:
    record_id: str
    account_id: str | None = None
    platform: str = ""
    core_production: str = "NOT_CONFIGURED"
    post_production: str = "NOT_VERIFIED"
    full_loop: str = "NOT_VERIFIED"
    checks: dict[str, str] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.core_production not in READINESS_STATES:
            raise ValueError(f"invalid core_production: {self.core_production}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.record_id


@dataclass(frozen=True)
class PlatformConnection:
    """External platform connection. Never Creator Identity."""

    connection_id: str
    creator_account_id: str
    platform: str
    provider: str = ""
    external_account_id: str = ""
    connection_status: str = "NOT_CONNECTED"
    credential_ref: str = ""
    social_account_id: str | None = None
    verified_capabilities: tuple[str, ...] = ()
    last_verified_at: str | None = None
    blocked_reason: str = ""
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.platform not in ACCOUNT_PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if self.connection_status not in CONNECTION_STATES:
            raise ValueError(f"invalid connection status: {self.connection_status}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.connection_id

    @property
    def connected(self) -> bool:
        return self.connection_status in {"CONNECTED", "VERIFIED", "DEGRADED"}


@dataclass(frozen=True)
class CreatorStrategy:
    strategy_id: str
    creator_account_id: str
    version: int = 1
    objective: str = ""
    positioning: str = ""
    audience: str = ""
    content_pillars: tuple[str, ...] = ()
    pillar_weights: dict[str, float] = field(default_factory=dict)
    content_mix: dict[str, float] = field(default_factory=dict)
    growth_goal: str = ""
    commercial_goal: str = ""
    experimentation_policy: str = ""
    continuity_policy: str = ""
    visual_policy: str = ""
    copy_policy: str = ""
    quality_bar: str = ""
    status: str = "ACTIVE"
    reason: str = ""
    effective_from: str | None = None
    effective_until: str | None = None
    supersedes_strategy_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.status not in STRATEGY_STATES:
            raise ValueError(f"invalid strategy status: {self.status}")
        if not self.effective_from:
            object.__setattr__(self, "effective_from", utcnow())
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)
        if not self.pillar_weights and self.content_pillars:
            share = round(1.0 / len(self.content_pillars), 4)
            object.__setattr__(self, "pillar_weights", {name: share for name in self.content_pillars})
        if not self.content_mix and self.pillar_weights:
            mix = dict(self.pillar_weights)
            if "experiment" not in {key.lower() for key in mix}:
                mix["Experiment"] = 0.1
            object.__setattr__(self, "content_mix", mix)

    @property
    def id(self) -> str:
        return self.strategy_id

    def snapshot(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "version": self.version,
            "objective": self.objective,
            "positioning": self.positioning,
            "audience": self.audience,
            "content_pillars": list(self.content_pillars),
            "pillar_weights": dict(self.pillar_weights),
            "content_mix": dict(self.content_mix),
            "growth_goal": self.growth_goal,
            "commercial_goal": self.commercial_goal,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class StrategyRevision:
    revision_id: str
    strategy_id: str
    creator_account_id: str
    version: int
    why_changed: str
    old_strategy: dict[str, Any] = field(default_factory=dict)
    new_strategy: dict[str, Any] = field(default_factory=dict)
    changed_by: str = "operator"
    supersedes_strategy_id: str | None = None
    effective_from: str | None = None
    changed_at: str | None = None

    def __post_init__(self) -> None:
        if not self.changed_at:
            object.__setattr__(self, "changed_at", utcnow())
        if not self.effective_from:
            object.__setattr__(self, "effective_from", self.changed_at)

    @property
    def id(self) -> str:
        return self.revision_id


@dataclass(frozen=True)
class CreatorState:
    state_id: str
    creator_account_id: str
    current_phase: str = ""
    current_objective: str = ""
    current_focus: str = ""
    current_series: str | None = None
    current_episode: str | None = None
    current_content_mix: dict[str, Any] = field(default_factory=dict)
    recent_topics: tuple[str, ...] = ()
    saturated_topics: tuple[str, ...] = ()
    underused_topics: tuple[str, ...] = ()
    current_strategy_id: str | None = None
    current_strategy_version: int | None = None
    current_character_version: int | None = None
    current_world_version: int | None = None
    last_production_at: str | None = None
    last_production_episode_id: str | None = None
    next_recommended_direction: str = ""
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)

    @property
    def id(self) -> str:
        return self.state_id

    def snapshot(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "creator_account_id": self.creator_account_id,
            "current_phase": self.current_phase,
            "current_objective": self.current_objective,
            "current_focus": self.current_focus,
            "current_series": self.current_series,
            "current_episode": self.current_episode,
            "current_content_mix": dict(self.current_content_mix),
            "recent_topics": list(self.recent_topics),
            "saturated_topics": list(self.saturated_topics),
            "underused_topics": list(self.underused_topics),
            "current_strategy_id": self.current_strategy_id,
            "current_strategy_version": self.current_strategy_version,
            "next_recommended_direction": self.next_recommended_direction,
            "last_production_episode_id": self.last_production_episode_id,
        }


@dataclass(frozen=True)
class ContentDecision:
    decision_id: str
    account_id: str
    platform: str
    strategy_id: str | None = None
    creator_state_id: str | None = None
    previous_episode_id: str | None = None
    selected_pillar: str = ""
    selected_topic: str = ""
    selected_angle: str = ""
    selected_format: str = "image"
    selected_scene: str = ""
    selected_emotion: str = ""
    selected_hook: str = ""
    idea_decision: str = "ACCEPT"
    reasoning: str = ""
    constraints: tuple[str, ...] = ()
    avoids: tuple[str, ...] = ()
    expected_effect: str = ""
    confidence: float = 0.5
    user_request: str = ""
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.idea_decision not in IDEA_DECISIONS:
            raise ValueError(f"invalid idea decision: {self.idea_decision}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    @property
    def id(self) -> str:
        return self.decision_id

    def snapshot(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "account_id": self.account_id,
            "platform": self.platform,
            "strategy_id": self.strategy_id,
            "selected_pillar": self.selected_pillar,
            "selected_topic": self.selected_topic,
            "selected_angle": self.selected_angle,
            "selected_format": self.selected_format,
            "selected_scene": self.selected_scene,
            "idea_decision": self.idea_decision,
            "reasoning": self.reasoning,
            "avoids": list(self.avoids),
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ContentPortfolioItem:
    item_id: str
    account_id: str
    pillar: str = ""
    topic: str = ""
    format: str = "image"
    scene: str = ""
    emotion: str = ""
    angle: str = ""
    hook: str = ""
    series_id: str | None = None
    episode_id: str | None = None
    date: str = ""
    status: str = "IDEA"
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.date:
            object.__setattr__(self, "date", (self.created_at or utcnow())[:10])

    @property
    def id(self) -> str:
        return self.item_id


@dataclass(frozen=True)
class ContentPortfolio:
    account_id: str
    platform: str
    items: tuple[ContentPortfolioItem, ...] = ()
    last_7_days: dict[str, int] = field(default_factory=dict)
    last_14_days: dict[str, int] = field(default_factory=dict)
    last_30_days: dict[str, int] = field(default_factory=dict)
    mix: dict[str, float] = field(default_factory=dict)
    created_at: str | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "platform": self.platform,
            "last_7_days": dict(self.last_7_days),
            "last_14_days": dict(self.last_14_days),
            "last_30_days": dict(self.last_30_days),
            "mix": dict(self.mix),
            "count": len(self.items),
        }


@dataclass(frozen=True)
class ContentSaturation:
    account_id: str
    topic: str = ""
    scene: str = ""
    angle: str = ""
    emotion: str = ""
    hook: str = ""
    topic_count: int = 0
    scene_count: int = 0
    angle_count: int = 0
    emotion_count: int = 0
    hook_count: int = 0
    action: str = "continue"
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.action not in SATURATION_ACTIONS:
            raise ValueError(f"invalid saturation action: {self.action}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    def snapshot(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "scene": self.scene,
            "angle": self.angle,
            "emotion": self.emotion,
            "action": self.action,
            "topic_count": self.topic_count,
            "scene_count": self.scene_count,
            "angle_count": self.angle_count,
        }


@dataclass(frozen=True)
class ContentNovelty:
    account_id: str
    verdict: str = "NOVEL"
    topic: str = "NOVEL"
    angle: str = "NOVEL"
    scene: str = "NOVEL"
    visual: str = "NOVEL"
    emotional: str = "NOVEL"
    narrative: str = "NOVEL"
    format: str = "NOVEL"
    hook: str = "NOVEL"
    reason: str = ""
    created_at: str | None = None

    def __post_init__(self) -> None:
        for name in ("verdict", "topic", "angle", "scene", "visual", "emotional", "narrative", "format", "hook"):
            value = getattr(self, name)
            if value not in NOVELTY_VERDICTS:
                raise ValueError(f"invalid novelty verdict for {name}: {value}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())

    def snapshot(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "topic": self.topic,
            "angle": self.angle,
            "scene": self.scene,
            "visual": self.visual,
            "emotional": self.emotional,
            "narrative": self.narrative,
            "format": self.format,
            "hook": self.hook,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ProductionMemory:
    memory_id: str
    account_id: str
    platform: str
    status: str = "CURRENT"
    strategy_id: str | None = None
    creator_state_id: str | None = None
    episode_id: str | None = None
    decision_id: str | None = None
    prompt_id: str | None = None
    character_id: str | None = None
    world_id: str | None = None
    series_id: str | None = None
    scene: str = ""
    asset_id: str | None = None
    visual_direction: str = ""
    copy_direction: str = ""
    what_was_produced: str = ""
    what_changed: str = ""
    what_worked: str = ""
    what_failed: str = ""
    what_should_continue: str = ""
    what_should_not_repeat: str = ""
    next_direction: str = ""
    confidence: float = 0.5
    importance: float = 0.5
    effective_from: str | None = None
    expires_at: str | None = None
    supersedes_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.status not in MEMORY_LIFECYCLE_STATES:
            raise ValueError(f"invalid production memory status: {self.status}")
        if not self.created_at:
            object.__setattr__(self, "created_at", utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)
        if not self.effective_from:
            object.__setattr__(self, "effective_from", self.created_at)

    @property
    def id(self) -> str:
        return self.memory_id

    def snapshot(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "account_id": self.account_id,
            "episode_id": self.episode_id,
            "decision_id": self.decision_id,
            "status": self.status,
            "what_was_produced": self.what_was_produced,
            "what_changed": self.what_changed,
            "what_should_continue": self.what_should_continue,
            "what_should_not_repeat": self.what_should_not_repeat,
            "next_direction": self.next_direction,
        }
