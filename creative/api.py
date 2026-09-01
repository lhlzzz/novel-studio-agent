"""Creative runtime API. Agents do not operate the store directly."""

from __future__ import annotations

from typing import Any

from creative.schemas import CreativeRun, CreativeTask, MediaAsset
from creative.workflow.engine import CreativeWorkflowEngine


class CreativeAPI:
    def __init__(self, engine: CreativeWorkflowEngine | None = None) -> None:
        self.engine = engine or CreativeWorkflowEngine()

    def create_run(self, workflow_id: str | None = None, inputs: dict[str, Any] | None = None, **kwargs: Any) -> CreativeRun:
        return self.engine.execute(workflow_id, inputs, **kwargs)

    def get_run(self, run_id: str) -> CreativeRun | None:
        return self.engine.store.get_run(run_id)

    def resume_run(self, run_id: str) -> CreativeRun:
        return self.engine.resume(run_id)

    def cancel_run(self, run_id: str) -> CreativeRun:
        return self.engine.cancel(run_id)

    def replay_run(self, run_id: str) -> CreativeRun:
        return self.engine.replay(run_id)

    def list_runs(self, status: str | None = None) -> list[CreativeRun]:
        return self.engine.store.list_runs(status)

    def get_task(self, task_id: str) -> CreativeTask | None:
        return self.engine.store.get_task(task_id)

    def list_assets(self, run_id: str | None = None) -> list[MediaAsset]:
        return self.engine.store.list_assets(run_id)

    def get_asset(self, asset_id: str) -> MediaAsset | None:
        return self.engine.store.get_asset(asset_id)
