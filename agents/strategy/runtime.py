"""Strategy agent runtime consumes memory and analytics insights."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from analytics.insights import recommend_next_change
from memory.retrieval import retrieve


@dataclass(frozen=True)
class StrategyPlan:
    objective: str
    audience: str
    content_pillars: tuple[str, ...]
    formats: tuple[str, ...]
    hooks: tuple[str, ...]
    cadence: str
    platform_variants: tuple[str, ...]
    experiment_plan: dict[str, Any]
    success_metrics: tuple[str, ...]


class StrategyAgent:
    name = "strategy-agent"
    owner = "strategy"
    capabilities = ("account", "topic", "experiment", "growth", "next_change", "plan")
    state_store = "postgres:agent_records"
    tests = ("tests/unit/test_agent_registry.py",)

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        memory = task.get("memory") or retrieve(task)
        insights = task.get("insights") or []
        research = task.get("research") or {}
        next_change = recommend_next_change(insights)
        plan = StrategyPlan(
            objective=str(task.get("objective") or "grow owned audience"),
            audience=str(task.get("audience") or ""),
            content_pillars=tuple(task.get("content_pillars") or ("proof", "process", "offer")),
            formats=tuple(task.get("formats") or ("post", "short")),
            hooks=tuple(task.get("hooks") or ((next_change.get("hook"),) if next_change.get("hook") else ())),
            cadence=str(task.get("cadence") or "3x weekly"),
            platform_variants=tuple(task.get("platforms") or ("x", "linkedin")),
            experiment_plan={
                "kinds": ("hook", "title", "posting_time"),
                "observation_window": str(task.get("observation_window") or "7d"),
                "sample_size": int(task.get("sample_size") or 30),
                "primary_metric": str(task.get("primary_metric") or "views"),
            },
            success_metrics=tuple(task.get("success_metrics") or ("views", "replies")),
        )
        return {
            "agent": self.name,
            "memory": memory,
            "next_change": next_change,
            "research": research,
            "plan": plan,
        }
