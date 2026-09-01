"""Select a workflow from a creative requirement. Agents choose; workflows execute."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from creative.schemas import CreativeWorkflow
from creative.workflow.registry import list_workflows, resolve_workflow


@dataclass
class ResolvedWorkflow:
    workflow: CreativeWorkflow
    workflow_id: str
    version: str
    reason: str
    requirements: dict[str, Any] = field(default_factory=dict)


class WorkflowResolver:
    def __init__(self, *, store=None) -> None:
        self.store = store

    def resolve(self, requirement: dict[str, Any], *, version: str | None = None) -> ResolvedWorkflow:
        history = None
        if self.store is not None:
            history = self.store.list_performance()
        workflow = resolve_from_requirement(requirement, performances=history)
        if version:
            workflow = resolve_workflow(workflow.workflow_id, version)
        return ResolvedWorkflow(
            workflow=workflow,
            workflow_id=workflow.workflow_id,
            version=workflow.version,
            reason="requirement",
            requirements=dict(requirement or {}),
        )


def requirement_text(requirement: dict[str, Any]) -> str:
    parts = [
        requirement.get("brief"),
        requirement.get("style"),
        requirement.get("category"),
        requirement.get("workflow_id"),
        " ".join(str(item) for item in (requirement.get("tags") or ())),
    ]
    return " ".join(str(item).lower() for item in parts if item)


def resolve_from_requirement(requirement: dict[str, Any], *, performances: list[dict[str, Any]] | None = None) -> CreativeWorkflow:
    explicit = requirement.get("workflow_id")
    if explicit:
        return resolve_workflow(str(explicit), requirement.get("workflow_version") or requirement.get("version"))
    text = requirement_text(requirement)
    if "drama" in text or "短剧" in text:
        return resolve_workflow("short-drama-v1")
    if "storyboard" in text or "分镜" in text:
        return resolve_workflow("scene-storyboard-v1")
    if "cinematic" in text:
        return resolve_workflow("cinematic-video-v1")
    if "ugc" in text:
        return resolve_workflow("ugc-style-video-v1")
    if requirement.get("commerce_intent") not in {None, "", "none"}:
        return resolve_workflow("product-optional-content-v1")
    if requirement.get("character_id") and ("consistency" in text or "角色" in text):
        return resolve_workflow("character-consistency-v1")
    if "lifestyle" in text or "生活" in text or requirement.get("face_visible") is False:
        return resolve_workflow("creator-lifestyle-v1")
    selected = resolve_workflow("creator-image-to-video-v1")
    if performances:
        ranked = WorkflowRanker().rank(performances)
        for item in ranked:
            if item.get("sample_size", 99) and item.get("workflow_id"):
                try:
                    return resolve_workflow(str(item["workflow_id"]))
                except Exception:
                    continue
    return selected


class WorkflowRanker:
    def rank(self, performances: list[dict[str, Any]]) -> list[dict[str, Any]]:
        scored = []
        for item in performances:
            quality = float(item.get("quality_score") or 0)
            engagement = float(item.get("engagement") or 0)
            cost = float(item.get("cost") or 1)
            latency = float(item.get("latency") or 1)
            score = quality * 0.5 + engagement * 0.3 - min(cost, 50) * 0.15 - min(latency, 120) * 0.05
            scored.append({**item, "workflow_score": round(score, 4)})
        return sorted(scored, key=lambda item: item["workflow_score"], reverse=True)


def list_candidates(requirement: dict[str, Any]) -> list[CreativeWorkflow]:
    tags = set(requirement.get("tags") or [])
    workflows = list_workflows()
    if not tags:
        return workflows
    return [item for item in workflows if tags.intersection(item.tags)] or workflows
