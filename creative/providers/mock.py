"""Deterministic generation backend for tests. Never reported as live Lechuang."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from creative.assets import MIN_PNG, AssetStore
from creative.errors import UnsupportedCapability
from creative.providers.base import CapabilityMixin
from creative.schemas import ProviderTask, utcnow

ALL_CAPABILITIES = frozenset({
    "generate_text",
    "generate_image",
    "edit_image",
    "generate_video",
    "extend_video",
    "edit_video",
    "upload_asset",
})


class MockGenerationProvider(CapabilityMixin):
    name = "mock"
    supported = ALL_CAPABILITIES

    def __init__(self, *, store: AssetStore | None = None, polls_until_done: int = 0, costs: dict[str, float] | None = None) -> None:
        self.store = store or AssetStore()
        self.polls_until_done = polls_until_done
        self.costs = costs or {
            "generate_image": 1.0,
            "edit_image": 1.0,
            "generate_video": 8.0,
            "extend_video": 6.0,
            "edit_video": 4.0,
            "generate_text": 0.1,
            "upload_asset": 0.0,
        }
        self._tasks: dict[str, ProviderTask] = {}

    def estimate(self, kind: str, payload: dict[str, Any] | None = None) -> float:
        n = int((payload or {}).get("variant_index", 0)) >= 0
        return float(self.costs.get(kind, 1.0)) * (1 if n else 1)

    def create_task(self, kind: str, payload: dict[str, Any]) -> ProviderTask:
        if kind not in self.supported:
            raise UnsupportedCapability(kind, provider=self.name)
        task_id = uuid4().hex
        status = "succeeded" if self.polls_until_done <= 0 else "queued"
        result = self._result(kind, payload) if status == "succeeded" else {}
        task = ProviderTask(provider=self.name, provider_task_id=task_id, status=status, kind=kind, result=result)
        self._tasks[task_id] = task
        return task

    def get_task(self, provider_task_id: str) -> ProviderTask:
        task = self._tasks[provider_task_id]
        poll = task.poll_count + 1
        if task.status in {"queued", "running"} and poll >= self.polls_until_done:
            result = self._result(task.kind, {})
            task = ProviderTask(
                provider=self.name,
                provider_task_id=task.provider_task_id,
                status="succeeded",
                kind=task.kind,
                result=result,
                poll_count=poll,
            )
        else:
            task = ProviderTask(
                provider=task.provider,
                provider_task_id=task.provider_task_id,
                status="running" if task.status == "queued" else task.status,
                kind=task.kind,
                result=task.result,
                error=task.error,
                poll_count=poll,
            )
        self._tasks[provider_task_id] = task
        return task

    def cancel_task(self, provider_task_id: str) -> ProviderTask:
        task = self._tasks[provider_task_id]
        task = ProviderTask(
            provider=self.name,
            provider_task_id=provider_task_id,
            status="cancelled",
            kind=task.kind,
            result=task.result,
            poll_count=task.poll_count,
        )
        self._tasks[provider_task_id] = task
        return task

    def get_result(self, provider_task_id: str) -> dict[str, Any]:
        task = self.get_task(provider_task_id)
        if task.status != "succeeded":
            return {"status": task.status, "error": task.error}
        return task.result

    def _result(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(payload.get("run_id") or "")
        workflow_id = str(payload.get("workflow_id") or "")
        workflow_version = str(payload.get("workflow_version") or "")
        character_id = payload.get("character_id")
        if kind in {"generate_text"}:
            return {"text": str(payload.get("prompt") or "scene plan"), "created_at": utcnow()}
        if kind in {"generate_image", "edit_image", "upload_asset"}:
            width = int(payload.get("width") or 720)
            height = int(payload.get("height") or 1280)
            blob = MIN_PNG + str(payload.get("variant_index") or 0).encode() + str(payload.get("prompt") or "").encode()
            asset = self.store.save_generated(
                blob,
                asset_type="image",
                suffix=".png",
                mime_type="image/png",
                width=width,
                height=height,
                workflow_id=workflow_id,
                workflow_version=workflow_version,
                creative_run_id=run_id,
                character_id=character_id,
                metadata={"kind": kind, "provider": self.name, "prompt": payload.get("prompt")},
            )
            return {"asset": asset, "credits_actual": self.costs.get(kind, 1.0)}
        duration = float(payload.get("duration_seconds") or 15)
        asset = self.store.save_generated(
            b"mock-mp4-bytes" + str(payload.get("variant_index") or 0).encode() + str(payload.get("prompt") or "").encode() + str(payload.get("reference") or "").encode(),
            asset_type="video",
            suffix=".mp4",
            mime_type="video/mp4",
            width=int(payload.get("width") or 720),
            height=int(payload.get("height") or 1280),
            duration=duration,
            fps=24,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            creative_run_id=run_id,
            character_id=character_id,
            metadata={"kind": kind, "provider": self.name, "prompt": payload.get("prompt"), "mode": payload.get("mode")},
        )
        return {"asset": asset, "credits_actual": self.costs.get(kind, 8.0)}
