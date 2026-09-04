"""Canonical creative objects. Provider payloads do not live here."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any


NODE_ALIASES = {
    "image.generate": "image_generate",
    "image.transform": "image_edit",
    "video.from_image": "video_generate",
    "video.generate": "video_generate",
}

NODE_TYPES = (
    "input",
    "text",
    "prompt",
    "reference",
    "character",
    "image_generate",
    "image.generate",
    "image_edit",
    "image.transform",
    "image_analyze",
    "image_crop",
    "image_split",
    "image_resize",
    "image_upscale",
    "image_annotate",
    "multi_angle",
    "video_generate",
    "video.generate",
    "video.from_image",
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


def _node_spec(*, status: str, requires: tuple[str, ...] = (), cost_class: str = "none", async_node: bool = False, reason: str = "", input_schema: dict[str, Any] | None = None, output_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "input_schema": dict(input_schema or {}),
        "output_schema": dict(output_schema or {}),
        "required_capabilities": requires,
        "provider_requirements": requires,
        "cost_class": cost_class,
        "async": async_node,
        "retry_policy": {"retryable": async_node, "on": ("timeout", "429", "5xx") if async_node else ()},
        "idempotency_policy": "run_id:node_id:attempt",
        "reason": reason,
        "requires": requires,
    }


NODE_REGISTRY: dict[str, dict[str, Any]] = {
    "input": {"status": NODE_STATUS_IMPLEMENTED},
    "text": {"status": NODE_STATUS_IMPLEMENTED},
    "prompt": {"status": NODE_STATUS_IMPLEMENTED},
    "reference": {"status": NODE_STATUS_IMPLEMENTED},
    "character": {"status": NODE_STATUS_IMPLEMENTED},
    "image_generate": _node_spec(status=NODE_STATUS_IMPLEMENTED, requires=("text_to_image", "image_generation"), cost_class="image", async_node=True, input_schema={"prompt": "str", "negative_prompt": "str", "aspect_ratio": "str", "resolution": "str", "reference_assets": "list", "seed": "int", "style": "str"}, output_schema={"asset_ids": "list"}),
    "image_edit": _node_spec(status=NODE_STATUS_IMPLEMENTED, requires=("image_to_image",), cost_class="image", async_node=True, input_schema={"source_asset": "str", "prompt": "str", "mask": "str", "reference_assets": "list"}, output_schema={"asset_ids": "list"}),
    "image_analyze": {"status": NODE_STATUS_IMPLEMENTED, "requires": ("vision_judge",)},
    "image_crop": {"status": NODE_STATUS_IMPLEMENTED},
    "image_split": {"status": NODE_STATUS_IMPLEMENTED},
    "image_resize": {"status": NODE_STATUS_IMPLEMENTED},
    "image_upscale": _node_spec(status=NODE_STATUS_BLOCKED, reason="super-resolution requires a verified provider capability"),
    "image_annotate": {"status": NODE_STATUS_IMPLEMENTED},
    "multi_angle": {"status": NODE_STATUS_IMPLEMENTED, "requires": ("text_to_image",)},
    "video_generate": _node_spec(status=NODE_STATUS_IMPLEMENTED, requires=("text_to_video", "image_to_video", "video_generation"), cost_class="video", async_node=True, input_schema={"source_image": "str", "prompt": "str", "duration": "number", "aspect_ratio": "str", "motion": "str", "camera": "str"}, output_schema={"asset_ids": "list"}),
    "video_extend": {"status": NODE_STATUS_IMPLEMENTED, "requires": ("video_extend",)},
    "video_edit": {"status": NODE_STATUS_IMPLEMENTED, "requires": ("video_edit",)},
    "audio": _node_spec(status=NODE_STATUS_BLOCKED, reason="no verified audio provider", requires=("audio_generation",)),
    "subtitle": {"status": NODE_STATUS_IMPLEMENTED},
    "render": {"status": NODE_STATUS_IMPLEMENTED},
    "judge": {"status": NODE_STATUS_IMPLEMENTED, "requires": ("vision_judge",)},
    "output": {"status": NODE_STATUS_IMPLEMENTED},
    "motion_annotation": {"status": NODE_STATUS_IMPLEMENTED},
    "storyboard": {"status": NODE_STATUS_IMPLEMENTED},
    "image.generate": None,
    "image.transform": None,
    "video.from_image": None,
    "video.generate": None,
}
NODE_REGISTRY["image.generate"] = {**NODE_REGISTRY["image_generate"], "canonical": "image_generate"}
NODE_REGISTRY["image.transform"] = {**NODE_REGISTRY["image_edit"], "canonical": "image_edit"}
NODE_REGISTRY["video.from_image"] = {**NODE_REGISTRY["video_generate"], "canonical": "video_generate", "required_capabilities": ("image_to_video",)}
NODE_REGISTRY["video.generate"] = {**NODE_REGISTRY["video_generate"], "canonical": "video_generate"}


class NodeRegistry:
    """Unique owner of production node contracts."""

    def __init__(self, specs: dict[str, dict[str, Any]] | None = None) -> None:
        self._specs = dict(specs or NODE_REGISTRY)

    def get(self, node_type: str) -> dict[str, Any]:
        spec = self._specs.get(node_type)
        if not spec:
            spec = self._specs.get(canonicalize_node_type(node_type), {})
        return spec or {}

    def require(self, node_type: str) -> dict[str, Any]:
        spec = self.get(node_type)
        if not spec:
            from creative.errors import WorkflowInvalid
            raise WorkflowInvalid(f"unknown node: {node_type}")
        if spec.get("status") == NODE_STATUS_BLOCKED:
            from creative.errors import ProviderBlocked
            raise ProviderBlocked(node_type, spec.get("reason") or "node blocked")
        return spec

    def types(self) -> tuple[str, ...]:
        return tuple(self._specs)


NODES = NodeRegistry()


def canonicalize_node_type(node_type: str) -> str:
    return NODE_ALIASES.get(node_type, node_type)

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
    "JUDGING": {"RUNNING", "WAITING_PROVIDER", "SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"},
    "BLOCKED": {"QUEUED", "CANCELLED"},
    "SUCCEEDED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}

TASK_STATES = ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED", "TIMEOUT", "UNKNOWN", "BLOCKED")

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
    "thumbnail",
    "cover",
    "reference_image",
    "character_reference",
    "video_reference",
)

REGENERATION_STRATEGIES = ("change_prompt", "change_variation", "change_reference", "change_camera", "change_model")

FAILURE_CODES = (
    "CAPABILITY_UNAVAILABLE",
    "PROVIDER_UNAVAILABLE",
    "PROVIDER_AUTH_MISSING",
    "PROVIDER_CONTRACT_UNVERIFIED",
    "BUDGET_EXCEEDED",
    "POLICY_REJECTED",
    "INVALID_WORKFLOW",
    "INVALID_INPUT",
    "RESEARCH_UNAVAILABLE",
    "DISTRIBUTION_UNAVAILABLE",
    "JUDGE_UNAVAILABLE",
    "PROVIDER_BLOCKED",
    "PROVIDER_ERROR",
    "AUTH_ERROR",
    "RATE_LIMIT",
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
        "timeout": "TIMEOUT",
        "unknown": "UNKNOWN",
        "blocked": "BLOCKED",
    }
    return lookup.get(raw.lower(), raw.upper() if raw else "UNKNOWN")


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


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    source: str
    latest_version: str
    name: str = ""


@dataclass(frozen=True)
class WorkflowVersion:
    workflow_id: str
    version: str
    snapshot: dict[str, Any]
    source: str = "template"
    name: str = ""


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
    blocked_reason: str | None = None
    blocked_message: str | None = None
    blocked_at: str | None = None
    retryable: bool = False


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
    account_id: str | None = None
    series_id: str | None = None
    episode_id: str | None = None
    content_package_id: str | None = None
    creative_context_id: str | None = None
    world_id: str | None = None
    provider: str = ""
    provider_task_id: str = ""
    model: str = ""


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
    passed: bool = False
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    latency_ms: float = 0.0
    cost: float | None = None

    def __post_init__(self) -> None:
        if self.decision == "PASS" and not self.passed:
            object.__setattr__(self, "passed", True)
        if self.decision != "PASS" and self.passed:
            object.__setattr__(self, "passed", False)


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
    input_units: float = 0.0
    output_units: float = 0.0
    duration_ms: float = 0.0
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    request_id: str = ""
    currency: str = "credits"


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
class CreativeResult:
    status: str
    asset_id: str | None = None
    provider: str = ""
    provider_task_id: str = ""
    error: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


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
