"""Workflow registry. Templates live here so video graphs do not become agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from creative.errors import WorkflowInvalid, WorkflowNotFound
from creative.schemas import CreativeWorkflow, WorkflowEdge, WorkflowNode, canonicalize_node_type, utcnow

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

TEMPLATES_DIR = Path(__file__).with_name("templates")
_REGISTRY: dict[str, dict[str, CreativeWorkflow]] = {}


def workflow_from_dict(data: dict[str, Any]) -> CreativeWorkflow:
    nodes = []
    for item in data.get("nodes") or []:
        node_type = canonicalize_node_type(str(item["type"]))
        if node_type not in __import__("creative.schemas", fromlist=["NODE_TYPES"]).NODE_TYPES and str(item["type"]) not in __import__("creative.schemas", fromlist=["NODE_TYPES"]).NODE_TYPES:
            raise ValueError(f"unknown node type: {node_type}")
        nodes.append(WorkflowNode(
            node_id=str(item["node_id"]),
            type=node_type,
            provider=item.get("provider"),
            model=item.get("model"),
            config=dict(item.get("config") or {}),
            inputs=dict(item.get("inputs") or {}),
        ))
    edges = tuple(
        WorkflowEdge(
            source_node=str(item["source_node"]),
            source_output=str(item.get("source_output") or "output"),
            target_node=str(item["target_node"]),
            target_input=str(item.get("target_input") or "input"),
        )
        for item in data.get("edges") or []
    )
    now = utcnow()
    return CreativeWorkflow(
        workflow_id=str(data["workflow_id"]),
        name=str(data.get("name") or data["workflow_id"]),
        description=str(data.get("description") or ""),
        version=str(data.get("version") or "1.0.0"),
        category=str(data.get("category") or "video"),
        inputs=dict(data.get("inputs") or {}),
        nodes=tuple(nodes),
        edges=edges,
        variables=dict(data.get("variables") or {}),
        provider_bindings=dict(data.get("provider_bindings") or {}),
        quality_policy=dict(data.get("quality_policy") or {}),
        outputs=dict(data.get("outputs") or {}),
        created_at=str(data.get("created_at") or now),
        updated_at=str(data.get("updated_at") or now),
        tags=tuple(data.get("tags") or ()),
    )


def register_workflow(workflow: CreativeWorkflow) -> CreativeWorkflow:
    versions = _REGISTRY.setdefault(workflow.workflow_id, {})
    existing = versions.get(workflow.version)
    if existing is not None:
        current = existing.export()
        incoming = workflow.export()
        for key in ("created_at", "updated_at", "providers"):
            current.pop(key, None)
            incoming.pop(key, None)
        if current != incoming:
            raise WorkflowInvalid(f"workflow version immutable: {workflow.workflow_id}@{workflow.version}")
        return existing
    versions[workflow.version] = workflow
    return workflow


def resolve_workflow(workflow_id: str, version: str | None = None) -> CreativeWorkflow:
    load_templates()
    versions = _REGISTRY.get(workflow_id)
    if not versions:
        raise WorkflowNotFound(workflow_id)
    if version:
        workflow = versions.get(version)
        if workflow is None:
            raise WorkflowNotFound(f"{workflow_id}@{version}")
        return workflow
    return versions[sorted(versions)[-1]]


def get_workflow_version(workflow_id: str, version: str) -> CreativeWorkflow:
    return resolve_workflow(workflow_id, version)


def list_workflows() -> list[CreativeWorkflow]:
    load_templates()
    return [resolve_workflow(workflow_id) for workflow_id in sorted(_REGISTRY)]


def load_templates(path: Path | None = None) -> list[CreativeWorkflow]:
    directory = path or TEMPLATES_DIR
    loaded = []
    if yaml is None or not directory.exists():
        return loaded
    for file in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
        workflow = workflow_from_dict(data)
        register_workflow(workflow)
        loaded.append(workflow)
    return loaded


def load_from_store(store) -> list[CreativeWorkflow]:
    loaded = []
    if store is None or not hasattr(store, "list_workflow_versions"):
        return loaded
    try:
        rows = store.list_workflow_versions()
    except Exception:
        return loaded
    for row in rows:
        snapshot = row.get("snapshot") or {}
        if not snapshot.get("workflow_id"):
            continue
        workflow = workflow_from_dict(snapshot)
        register_workflow(workflow)
        loaded.append(workflow)
    return loaded
