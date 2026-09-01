"""Poll provider tasks from PostgreSQL. Agents never sleep on generation."""

from __future__ import annotations

from uuid import uuid4

from creative.workflow.engine import CreativeWorkflowEngine


def run_once(*, engine: CreativeWorkflowEngine | None = None, worker_id: str | None = None) -> list[str]:
    worker = worker_id or f"worker-{uuid4().hex[:8]}"
    engine = engine or CreativeWorkflowEngine.production(worker_id=worker)
    resumed = []
    for run in engine.store.list_recoverable_runs():
        if not engine.store.acquire_lease(run.run_id, worker):
            continue
        engine.resume(run.run_id, worker_id=worker)
        resumed.append(run.run_id)
        engine.store.release_lease(run.run_id, worker)
    return resumed
