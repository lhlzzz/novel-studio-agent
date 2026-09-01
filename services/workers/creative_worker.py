"""Poll provider tasks. Agents never sleep on generation."""

from __future__ import annotations

from typing import Any

from creative.workflow.engine import CreativeWorkflowEngine


def run_once(*, engine: CreativeWorkflowEngine | None = None) -> list[str]:
    engine = engine or CreativeWorkflowEngine()
    resumed = []
    for run in engine.store.list_runs("WAITING_PROVIDER"):
        engine.resume(run.run_id)
        resumed.append(run.run_id)
    return resumed
