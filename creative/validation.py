"""Fail closed before a workflow is allowed to spend credits."""

from __future__ import annotations

from creative.errors import WorkflowInvalid
from creative.schemas import NODE_REGISTRY, NODE_STATUS_BLOCKED, NODE_TYPES, CreativeWorkflow

COMPATIBLE = {
    "image": {"image", "video", "reference", "final", "asset", "output", "clip"},
    "video": {"video", "final", "asset", "output", "clip"},
    "text": {"text", "prompt", "brief", "output", "input"},
    "prompt": {"prompt", "text", "output", "input"},
    "audio": {"audio", "video"},
    "subtitle": {"subtitle", "video"},
}

PRODUCES = {
    "input": "text",
    "text": "text",
    "prompt": "prompt",
    "reference": "image",
    "character": "text",
    "image_generate": "image",
    "image_edit": "image",
    "image_analyze": "image",
    "image_crop": "image",
    "image_split": "image",
    "image_resize": "image",
    "image_annotate": "image",
    "multi_angle": "image",
    "video_generate": "video",
    "video_extend": "video",
    "video_edit": "video",
    "subtitle": "subtitle",
    "render": "video",
    "judge": "image",
    "output": "video",
    "motion_annotation": "image",
    "storyboard": "text",
}


def validate_workflow(workflow: CreativeWorkflow, inputs: dict | None = None) -> None:
    reasons: list[str] = []
    ids = [node.node_id for node in workflow.nodes]
    if len(ids) != len(set(ids)):
        reasons.append("node id not unique")
    known = set(ids)
    for node in workflow.nodes:
        if node.type not in NODE_TYPES:
            reasons.append(f"unknown node: {node.type}")
        spec = NODE_REGISTRY.get(node.type) or {}
        if spec.get("status") == NODE_STATUS_BLOCKED:
            reasons.append(f"blocked node registered: {node.type}")
    for edge in workflow.edges:
        if edge.source_node not in known:
            reasons.append(f"invalid edge source: {edge.source_node}")
        if edge.target_node not in known:
            reasons.append(f"invalid edge target: {edge.target_node}")
        source = next((item for item in workflow.nodes if item.node_id == edge.source_node), None)
        target = next((item for item in workflow.nodes if item.node_id == edge.target_node), None)
        if source and target:
            produced = PRODUCES.get(source.type, "text")
            allowed = COMPATIBLE.get(produced, {produced, "output", "asset"})
            if target.type == "image_generate" and produced == "audio":
                reasons.append("incompatible: audio cannot feed image prompt")
            if produced == "audio" and target.type in {"image_generate", "image_edit", "prompt"}:
                reasons.append("incompatible: audio -> image prompt")
    order, cycle = topo_sort(workflow)
    if cycle:
        reasons.append("cycle")
    reachable = {node.node_id for node in order}
    if known - reachable:
        reasons.append("unreachable node")
    if inputs:
        for name, spec in (workflow.inputs or {}).items():
            if isinstance(spec, dict) and spec.get("required") and name not in inputs:
                reasons.append(f"missing input: {name}")
        if workflow.inputs and "brief" in workflow.inputs and not (inputs.get("brief") or inputs.get("script") or inputs.get("text")):
            spec = workflow.inputs.get("brief")
            if isinstance(spec, dict) and spec.get("required"):
                reasons.append("missing input: brief")
    if reasons:
        raise WorkflowInvalid(reasons)
    return None


def topo_sort(workflow: CreativeWorkflow) -> tuple[list, bool]:
    inbound = {node.node_id: 0 for node in workflow.nodes}
    outgoing: dict[str, list[str]] = {node.node_id: [] for node in workflow.nodes}
    for edge in workflow.edges:
        if edge.target_node in inbound and edge.source_node in inbound:
            inbound[edge.target_node] += 1
            outgoing.setdefault(edge.source_node, []).append(edge.target_node)
    ready = [node for node in workflow.nodes if inbound[node.node_id] == 0]
    ordered = []
    seen: set[str] = set()
    while ready:
        node = ready.pop(0)
        if node.node_id in seen:
            continue
        seen.add(node.node_id)
        ordered.append(node)
        for target in outgoing.get(node.node_id, []):
            inbound[target] -= 1
            if inbound[target] == 0:
                ready.extend([item for item in workflow.nodes if item.node_id == target])
    cycle = len(ordered) != len(workflow.nodes)
    return ordered, cycle
