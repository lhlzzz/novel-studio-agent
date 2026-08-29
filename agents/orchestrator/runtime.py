"""Orchestrator runtime coordinates capability agents. It does not call providers."""

from __future__ import annotations

from typing import Any

from agents.registry import resolve_agent
from governance.observability import log_event, new_request_id


class OrchestratorAgent:
    name = "meiti-orchestrator"
    owner = "coordination"
    capabilities = ("coordinate", "weekly_plan", "publish_request", "performance_review")
    state_store = "postgres:agent_runs"
    tests = ("tests/unit/test_agent_registry.py",)

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        request_id = str(task.get("request_id") or new_request_id())
        kind = str(task.get("kind") or "coordinate")
        payload = {**task, "request_id": request_id}
        research = resolve_agent("research-agent").implementation.run(payload) if kind in {"weekly_plan", "coordinate"} else {}
        memory = resolve_agent("memory-agent").implementation.retrieve(payload)
        strategy = resolve_agent("strategy-agent").implementation.run({**payload, "research": research, "memory": memory})
        content = resolve_agent("content-agent").implementation.run({**payload, "strategy": strategy, "memory": memory})
        log_event(agent=self.name, action=kind, status="ok", request_id=request_id)
        return {
            "agent": self.name,
            "request_id": request_id,
            "research": research,
            "strategy": strategy,
            "content": content,
            "memory": memory,
        }
