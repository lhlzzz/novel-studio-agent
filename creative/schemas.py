"""Canonical creative objects. Provider payloads do not live here."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any


NODE_TYPES = (
    "input",
    "text",
    "prompt",
    "reference",
    "character",
    "image_generate",
    "image_edit",
    "image_analyze",
    "image_crop",
    "image_split",
    "image_resize",
    "image_upscale",
    "image_annotate",
    "multi_angle",
    "video_generate",
    "video_extend",
    "video_edit",
    "audio",
    "subtitle",
    "render",
    "judge",
    "output",
    "motion_annotation",
    "storyboard",
)

NODE_STATUS_IMPLEMENTED = "IMPLEMENTED"
NODE_STATUS_VERIFIED = "VERIFIED"
NODE_STATUS_BLOCKED = "BLOCKED"

NODE_REGISTRY: dict[str, dict[str, Any]] = {
    "input": {"status": NODE_STATUS_IMPLEMENTED},
    "text": {"status": NODE_STATUS_IMPLEMENTED},
    "prompt": {"status": NODE_STATUS_IMPLEMENTED},
    "reference": {"status": NODE_STATUS_IMPLEMENTED},
    "character": {"status": NODE_STATUS_IMPLEMENTED},
    "image_generate": {"status": NODE_STATUS_IMPLEMENTED, "requires": ("text_to_image",)},
    "image_edit": {"status": NODE_STATUS_IMPLEMENTED, "requires": ("image_to_image",)},
    "image_analyze": {"status": NODE_STATUS_IMPLEMENTED, "requires": ("vision_judge",)},
    "image_crop": {"status": NODE_STATUS_IMPLEMENTED},
    "image_split": {"status": NODE_STATUS_IMPLEMENTED},
    "image_resize": {"status": NODE_STATUS_IMPLEMENTED},
    "image_upscale": {"status": NODE_STATUS_BLOCKED, "reason": "super-resolution requires a verified provider capability"},
    "image_annotate": {"status": NODE_STATUS_IMPLEMENTED},
    "multi_angle": {"status": NODE_STATUS_IMPLEMENTED, "requires": ("text_to_image",)},
    "video_generate": {"status": NODE_STATUS_IMPLEMENTED, "requires": ("text_to_video", "image_to_video")},
    "video_extend": {"status": NODE_STATUS_IMPLEMENTED, "requires": ("video_extend",)},
    "video_edit": {"status": NODE_STATUS_IMPLEMENTED, "requires": ("video_edit",)},
    "audio": {"status": NODE_STATUS_BLOCKED, "reason": "no verified audio provider"},
    "subtitle": {"status": NODE_STATUS_IMPLEMENTED},
    "render": {"status": NODE_STATUS_IMPLEMENTED},
    "judge": {"status": NODE_STATUS_IMPLEMENTED, "requires": ("vision_judge",)},
    "output": {"status": NODE_STATUS_IMPLEMENTED},
    "motion_annotation": {"status": NODE_STATUS_IMPLEMENTED},
    "storyboard": {"status": NODE_STATUS_IMPLEMENTED},
}

RUN_STATES = (
    "DRAFT",
    "QUEUED",
    "RUNNING",
    "WAITING_PROVIDER",
    "JUDGING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "BLOCKED",
)

RUN_TRANSITIONS = {
    "DRAFT": {"QUEUED", "RUNNING", "CANCELLED", "BLOCKED"},
    "QUEUED": {"RUNNING", "CANCELLED", "BLOCKED"},
    "RUNNING": {"WAITING_PROVIDER", "JUDGING", "SUCCEEDED", "FAILED", "CANCELLED", "BLOCKED"},
    "WAITING_PROVIDER": {"RUNNING", "JUDGING", "FAILED", "CANCELLED", "BLOCKED"},
    "JUDGING": {"RUNNING", "SUCCEEDED", "FAILED", "BLOCKED"},
    "BLOCKED": {"QUEUED", "CANCELLED"},
    "SUCCEEDED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}

TASK_STATES = ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED", "BLOCKED")

ASSET_TYPES = (
    "image",
    "video",
    "audio",
    "character",
    "reference",
    "prompt",
    "storyboard",
    "subtitle",
    "final",
)

REGENERATION_STRATEGIES = ("change_prompt", "change_variation", "change_reference", "change_camera", "change_model")

FAILURE_CODES = (
    "PROVIDER_BLOCKED",
    "PROVIDER_ERROR",
    "AUTH_ERROR",
    "RATE_LIMIT",
    "BUDGET_EXCEEDED",
    "WORKFLOW_INVALID",
    "QUALITY_FAILED",
    "TECHNICAL_MEDIA_FAILED",
    "TIMEOUT",
    "CANCELLED",
    "CREATIVE_PATTERN_FAILED",
)

CREATIVE_MEMORY_CODES = frozenset({"QUALITY_FAILED", "WORKFLOW_INVALID", "CREATIVE_PATTERN_FAILED"})

CROP_ASPECTS = ("1:1", "4:5", "3:4", "16:9", "9:16", "custom")

EVENT_TYPES = (
    "run_created",
    "node_started",
    "node_completed",
    "provider_submitted",
    "provider_completed",
    "judge_completed",
    "asset_created",
    "run_blocked",
    "run_failed",
    "run_completed",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: to_plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value


def map_task_status(status: str) -> str:
    raw = str(status or "queued").strip()
    lookup = {
        "queued": "QUEUED",
        "running": "RUNNING",
        "succeeded": "SUCCEEDED",
        "success": "SUCCEEDED",
        "failed": "FAILED",
        "cancelled": "CANCELLED",
        "canceled": "CANCELLED",
        "blocked": "BLOCKED",
    }
    return lookup.get(raw.lower(), raw.upper() if raw else "QUEUED")


@dataclass(frozen=True)
class WorkflowNode:
    node_id: str
    type: str
    provider: str | None = None
    model: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowEdge:
    source_node: str
    source_output: str
    target_node: str
    target_input: str


@dataclass(frozen=True)
class CreativeWorkflow:
    workflow_id: str
    name: str
    description: str
    version: str
    category: str
    inputs: dict[str, Any]
    nodes: tuple[WorkflowNode, ...]
    edges: tuple[WorkflowEdge, ...]
    variables: dict[str, Any] = field(default_factory=dict)
    provider_bindings: dict[str, Any] = field(default_factory=dict)
    quality_policy: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    tags: tuple[str, ...] = ()

    def node(self, node_id: str) -> WorkflowNode:
        for item in self.nodes:
            if item.node_id == node_id:
                return item
        raise KeyError(node_id)

    def export(self) -> dict[str, Any]:
        payload = to_plain(self)
        payload["providers"] = sorted({
            node.provider for node in self.nodes if node.provider
        })
        return payload


@dataclass
class CreativeRun:
    run_id: str
    workflow_id: str
    workflow_version: str
    status: str = "DRAFT"
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    budget: float | None = None
    idempotency_key: str | None = None
    workflow_snapshot: dict[str, Any] = field(default_factory=dict)
    judge_results: list[dict[str, Any]] = field(default_factory=list)
    asset_ids: list[str] = field(default_factory=list)
    task_ids: list[str] = field(default_factory=list)
    replay_of: str | None = None
    cursor: int = 0
    node_outputs: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, str] = field(default_factory=dict)
    worker_id: str | None = None
    lease_until: str | None = None
    heartbeat_at: str | None = None
    selected_asset_id: str | None = None
    selection_reason: str | None = None
    selection_score: float | None = None
    request_id: str | None = None
    error_code: str | None = None


@dataclass
class CreativeTask:
    task_id: str
    run_id: str
    node_id: str
    provider: str
    provider_task_id: str
    status: str = "QUEUED"
    poll_count: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    kind: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    attempt: int = 0
    timeout_at: str | None = None
    execution_key: str = ""


@dataclass(frozen=True)
class MediaAsset:
    asset_id: str
    type: str
    path: str
    sha256: str
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    fps: float | None = None
    mime_type: str = ""
    workflow_id: str | None = None
    workflow_version: str | None = None
    creative_run_id: str | None = None
    prompt_id: str | None = None
    character_id: str | None = None
    size: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    technical_score: float | None = None
    visual_score: float | None = None
    content_score: float | None = None
    platform_score: float | None = None
    overall_score: float | None = None


@dataclass(frozen=True)
class VisualDNA:
    face: str = ""
    hair: str = ""
    body: str = ""
    age_style: str = ""
    makeup: str = ""
    wardrobe_style: str = ""
    color_style: str = ""
    lighting_style: str = ""
    camera_style: str = ""


@dataclass(frozen=True)
class Character:
    character_id: str
    name: str
    visual_dna: VisualDNA = field(default_factory=VisualDNA)
    behavior_dna: str = ""
    style_dna: str = ""
    reference_assets: tuple[str, ...] = ()
    voice_assets: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class CameraPlan:
    movement: str = "static"
    framing: str = "medium"
    notes: str = ""


@dataclass(frozen=True)
class MotionPlan:
    camera: CameraPlan = field(default_factory=CameraPlan)
    character_motion: str = ""
    paths: tuple[dict[str, Any], ...] = ()
    labels: tuple[str, ...] = ()
    instructions: str = ""


@dataclass(frozen=True)
class Shot:
    shot_id: str
    duration: float = 3.0
    camera: CameraPlan = field(default_factory=CameraPlan)
    character_id: str | None = None
    scene: str = ""
    prompt: str = ""
    reference: str | None = None
    motion: MotionPlan = field(default_factory=MotionPlan)
    audio: str = ""


@dataclass(frozen=True)
class Storyboard:
    storyboard_id: str
    shots: tuple[Shot, ...] = ()


@dataclass(frozen=True)
class JudgeResult:
    score: float
    decision: str
    reasons: tuple[str, ...]
    judge_type: str
    judge_model: str
    judge_version: str
    breakdown: dict[str, float]
    timestamp: str
    asset_id: str | None = None
    judge_id: str | None = None
    judge_provider: str | None = None
    creative_run_id: str | None = None


@dataclass(frozen=True)
class GenerationUsage:
    usage_id: str
    provider: str
    model: str
    task: str
    input: dict[str, Any]
    output: dict[str, Any]
    credits_estimated: float
    credits_actual: float
    status: str
    timestamp: str
    run_id: str = ""
    node_id: str = ""


@dataclass(frozen=True)
class WorkflowPerformance:
    workflow_id: str
    version: str
    content_id: str = ""
    platform: str = ""
    quality_score: float | None = None
    engagement: float | None = None
    conversion: float | None = None
    cost: float | None = None
    latency: float | None = None
    run_id: str = ""
    asset_id: str = ""
    publication_id: str = ""
    provider: str = ""
    model: str = ""
    character: str = ""
    scene: str = ""
    motion: str = ""
    camera: str = ""
    duration: float | None = None


@dataclass(frozen=True)
class PromptAsset:
    prompt_id: str
    prompt: str
    negative_prompt: str = ""
    references: tuple[str, ...] = ()
    model: str = ""
    provider: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    workflow_id: str = ""
    workflow_version: str = ""
    version: str = "v1"
    family_id: str = ""


@dataclass(frozen=True)
class LechuangAssetReference:
    provider: str
    remote_id: str
    remote_url: str = ""


@dataclass(frozen=True)
class AssetReference:
    kind: str
    asset_id: str | None = None
    provider: str | None = None
    remote_id: str | None = None
    character_id: str | None = None
    url: str | None = None
    path: str | None = None


@dataclass(frozen=True)
class ProviderTask:
    provider: str
    provider_task_id: str
    status: str
    kind: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    poll_count: int = 0


@dataclass(frozen=True)
class ProviderQuote:
    credits: float
    currency: str = "credits"
    parameters: dict[str, Any] = field(default_factory=dict)
    valid_until: str | None = None
    mock: bool = False
    provider: str = ""
