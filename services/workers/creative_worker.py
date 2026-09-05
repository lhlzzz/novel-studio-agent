"""Poll provider tasks from PostgreSQL. Agents never sleep on generation."""

from __future__ import annotations

from uuid import uuid4

from creative.workflow.engine import CreativeWorkflowEngine


def run_once(*, engine: CreativeWorkflowEngine | None = None, worker_id: str | None = None, runtime=None) -> list[str]:
    worker = worker_id or f"worker-{uuid4().hex[:8]}"
    if engine is None:
        if runtime is None:
            from creative.runtime.container import CreativeRuntime
            runtime = CreativeRuntime.production(worker_id=worker)
        engine = runtime.engine
    resumed = []
    for run in engine.store.list_recoverable_runs():
        if run.status not in {"QUEUED", "RUNNING", "WAITING_PROVIDER", "JUDGING"}:
            continue
        if not engine.store.acquire_lease(run.run_id, worker):
            continue
        try:
            engine.store.heartbeat(run.run_id, worker)
            engine.resume(run.run_id, worker_id=worker)
            resumed.append(run.run_id)
        finally:
            current = engine.store.get_run(run.run_id) or run
            if current.status in {"SUCCEEDED", "FAILED", "CANCELLED", "BLOCKED", "WAITING_PROVIDER", "JUDGING", "QUEUED", "RUNNING"}:
                engine.store.release_lease(run.run_id, worker)
    return resumed


def reconcile_creator_jobs(*, continuity=None) -> list[dict]:
    if continuity is None:
        from content.runtime import ContinuityRuntime
        continuity = ContinuityRuntime.production()
    return continuity.reconcile_creative_jobs()
