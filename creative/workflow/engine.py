"""CreativeWorkflowEngine is the sole generation owner. Agents select; this executes."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from creative.assets import AssetStore
from creative.errors import BudgetExceeded, IllegalRunTransition, ProviderBlocked, QualityBlocked
from creative.judge import RegenerationStrategy
from creative.nodes import estimate_workflow_cost, execute_node, quality_gate
from creative.providers.resolver import GenerationProviderResolver
from creative.schemas import RUN_TRANSITIONS, CreativeRun, CreativeWorkflow, MediaAsset, to_plain, utcnow
from creative.workflow.registry import resolve_workflow
from creative.workflow.resolver import resolve_from_requirement


def make_idempotency_key(workflow_id: str, version: str, inputs: dict[str, Any]) -> str:
    payload = json.dumps({"workflow_id": workflow_id, "version": version, "inputs": inputs}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CreativeStore:
    def __init__(self, *, assets: AssetStore | None = None) -> None:
        self.assets = assets or AssetStore()
        self.runs: dict[str, CreativeRun] = {}
        self.tasks: dict[str, Any] = {}
        self.usage: dict[str, Any] = {}
        self.prompts: dict[str, Any] = {}
        self.performance: list[Any] = []
        self.by_idempotency: dict[str, str] = {}

    def save_run(self, run: CreativeRun) -> CreativeRun:
        self.runs[run.run_id] = run
        if run.idempotency_key:
            self.by_idempotency[run.idempotency_key] = run.run_id
        return run

    def get_run(self, run_id: str) -> CreativeRun | None:
        return self.runs.get(run_id)

    def get_by_idempotency(self, key: str) -> CreativeRun | None:
        run_id = self.by_idempotency.get(key)
        return self.runs.get(run_id) if run_id else None

    def save_task(self, task) -> None:
        self.tasks[task.task_id] = task

    def list_open_tasks(self, run_id: str):
        return [item for item in self.tasks.values() if item.run_id == run_id and item.status in {"queued", "running"}]

    def save_usage(self, usage) -> None:
        self.usage[usage.usage_id] = usage

    def save_prompt(self, prompt) -> None:
        self.prompts[prompt.prompt_id] = prompt

    def list_runs(self, status: str | None = None) -> list[CreativeRun]:
        runs = list(self.runs.values())
        if status:
            return [item for item in runs if item.status == status]
        return runs


def transition(run: CreativeRun, status: str) -> CreativeRun:
    allowed = RUN_TRANSITIONS.get(run.status, set())
    if status != run.status and status not in allowed:
        raise IllegalRunTransition(run.status, status)
    run.status = status
    if status == "RUNNING" and not run.started_at:
        run.started_at = utcnow()
    if status in {"SUCCEEDED", "FAILED", "CANCELLED", "BLOCKED"}:
        run.completed_at = utcnow()
    return run


def _topo(workflow: CreativeWorkflow) -> list:
    inbound = {node.node_id: 0 for node in workflow.nodes}
    outgoing: dict[str, list[str]] = {node.node_id: [] for node in workflow.nodes}
    for edge in workflow.edges:
        if edge.target_node in inbound:
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
    if len(ordered) != len(workflow.nodes):
        remaining = [node for node in workflow.nodes if node.node_id not in seen]
        ordered.extend(remaining)
    return ordered


class CreativeWorkflowEngine:
    def __init__(
        self,
        *,
        store: CreativeStore | None = None,
        resolver: GenerationProviderResolver | None = None,
        allow_mock: bool = False,
    ) -> None:
        self.store = store or CreativeStore()
        self.allow_mock = allow_mock
        self.resolver = resolver or GenerationProviderResolver(allow_mock=allow_mock)
        if allow_mock:
            from creative.providers.mock import MockGenerationProvider
            mock = self.resolver.providers.get("mock") or MockGenerationProvider(store=self.store.assets)
            if getattr(mock, "store", None) is not self.store.assets:
                mock = MockGenerationProvider(store=self.store.assets, polls_until_done=getattr(mock, "polls_until_done", 0))
                self.resolver.providers["mock"] = mock

    def select(self, requirement: dict[str, Any]) -> CreativeWorkflow:
        return resolve_from_requirement(requirement)

    def execute(
        self,
        workflow_id: str | None = None,
        inputs: dict[str, Any] | None = None,
        *,
        requirement: dict[str, Any] | None = None,
        budget: float | None = None,
        idempotency_key: str | None = None,
        replay_of: str | None = None,
        allow_mock: bool | None = None,
    ) -> CreativeRun:
        if allow_mock is not None:
            self.allow_mock = allow_mock
            self.resolver.allow_mock = allow_mock
        payload = dict(requirement or {})
        payload.update(inputs or {})
        workflow = resolve_workflow(workflow_id) if workflow_id else self.select(payload)
        key = None if replay_of else (idempotency_key or make_idempotency_key(workflow.workflow_id, workflow.version, payload))
        if key:
            existing = self.store.get_by_idempotency(key)
            if existing is not None:
                return existing
        run = CreativeRun(
            run_id=uuid4().hex,
            workflow_id=workflow.workflow_id,
            workflow_version=workflow.version,
            inputs=payload,
            budget=float(budget if budget is not None else payload.get("budget") or 40),
            idempotency_key=key,
            workflow_snapshot=workflow.export(),
            replay_of=replay_of,
        )
        run.estimated_cost = estimate_workflow_cost(workflow, payload)
        self.store.save_run(run)
        if run.budget is not None and run.estimated_cost > float(run.budget):
            run.error = f"estimated cost {run.estimated_cost} exceeds budget {run.budget}"
            transition(run, "BLOCKED")
            self.store.save_run(run)
            return run
        try:
            transition(run, "RUNNING")
            return self._advance(run, workflow)
        except ProviderBlocked as exc:
            run.error = str(exc)
            transition(run, "BLOCKED")
            self.store.save_run(run)
            return run
        except BudgetExceeded as exc:
            run.error = str(exc)
            transition(run, "BLOCKED")
            self.store.save_run(run)
            return run
        except Exception as exc:
            run.error = str(exc)
            transition(run, "FAILED")
            self.store.save_run(run)
            return run

    def replay(self, run_id: str, *, allow_mock: bool | None = None) -> CreativeRun:
        previous = self.store.get_run(run_id)
        if previous is None:
            raise KeyError(run_id)
        return self.execute(
            previous.workflow_id,
            dict(previous.inputs),
            replay_of=run_id,
            budget=previous.budget,
            allow_mock=self.allow_mock if allow_mock is None else allow_mock,
        )

    def resume(self, run_id: str) -> CreativeRun:
        run = self.store.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        workflow = resolve_workflow(run.workflow_id, run.workflow_version)
        self._poll_open_tasks(run)
        if run.status == "WAITING_PROVIDER" and not self.store.list_open_tasks(run.run_id):
            transition(run, "RUNNING")
        if run.status != "RUNNING":
            return run
        return self._advance(run, workflow)

    def _poll_open_tasks(self, run: CreativeRun) -> None:
        for task in self.store.list_open_tasks(run.run_id):
            provider, _ = self.resolver.resolve(task.provider if task.provider != "mock" else "mock")
            if task.provider == "lechuang" and self.allow_mock:
                provider, _ = self.resolver.resolve("lechuang")
            handle = provider.get_task(task.provider_task_id)
            task.poll_count = handle.poll_count
            task.status = handle.status
            task.result = dict(handle.result or {})
            task.error = handle.error
            if handle.status == "succeeded":
                task.completed_at = utcnow()
                asset = handle.result.get("asset")
                if isinstance(asset, MediaAsset):
                    self.store.assets.put(asset)
                    run.asset_ids.append(asset.asset_id)
                    node_out = run.node_outputs.setdefault(task.node_id, {"assets": [], "variants": []})
                    node_out.setdefault("assets", []).append(asset)
                    node_out["output"] = node_out["assets"][0]
                    node_out["asset"] = node_out["assets"][0]
                    node_out["variants"] = node_out["assets"]
            self.store.save_task(task)

    def _advance(self, run: CreativeRun, workflow: CreativeWorkflow) -> CreativeRun:
        order = _topo(workflow)
        context = dict(run.node_outputs)
        regen = RegenerationStrategy()
        while run.cursor < len(order):
            node = order[run.cursor]
            open_for_node = [item for item in self.store.list_open_tasks(run.run_id) if item.node_id == node.node_id]
            existing = context.get(node.node_id) or {}
            if open_for_node:
                transition(run, "WAITING_PROVIDER")
                self.store.save_run(run)
                return run
            if existing.get("asset") or existing.get("output") is not None and node.type in {"image_generate", "video_generate", "image_edit", "video_edit", "video_extend"}:
                if node.type in {"image_generate", "video_generate", "image_edit", "video_edit", "video_extend"} and existing.get("asset"):
                    run.cursor += 1
                    continue
            result = execute_node(node, workflow=workflow, run=run, context=context, store=self.store, resolver=self.resolver)
            if result.get("_pending"):
                run.node_outputs[node.node_id] = {key: value for key, value in result.items() if key != "_pending"}
                transition(run, "WAITING_PROVIDER")
                self.store.save_run(run)
                return run
            if node.type == "judge" and result.get("decision") == "FAIL":
                action = regen.next_action(int((run.outputs.get("regen_attempt") or 0)))
                run.outputs["regen_attempt"] = int(run.outputs.get("regen_attempt") or 0) + 1
                if action != "stop":
                    generate_index = max((index for index, item in enumerate(order[: run.cursor]) if item.type in {"image_generate", "video_generate"}), default=None)
                    if generate_index is not None:
                        run.cursor = generate_index
                        run.inputs = {**run.inputs, "variation_seed": action, "camera": "handheld" if action == "change_camera" else run.inputs.get("camera")}
                        continue
            context[node.node_id] = result
            run.node_outputs[node.node_id] = _plain_node(result)
            run.cursor += 1
        final = None
        for node in reversed(order):
            payload = context.get(node.node_id) or {}
            candidate = payload.get("asset") or payload.get("output")
            if isinstance(candidate, MediaAsset):
                final = candidate
                break
        assets = [self.store.assets.get(item) for item in run.asset_ids if self.store.assets.get(item)]
        gate = quality_gate(run, [item for item in assets if item is not None])
        run.quality = {key: str(value) for key, value in gate.items() if key != "reasons"}
        run.outputs = {
            "asset_id": final.asset_id if final else None,
            "assets": [item.asset_id for item in assets if item],
            "quality": run.quality,
            "estimated_cost": run.estimated_cost,
            "actual_cost": run.actual_cost,
        }
        if any(run.quality.get(key) != "pass" for key in ("visual_quality", "identity_quality", "technical_quality")):
            run.error = "quality gate blocked: " + ", ".join(gate.get("reasons") or [])
            transition(run, "BLOCKED")
        else:
            transition(run, "SUCCEEDED")
        self.store.save_run(run)
        return run

    def to_content_package(self, run: CreativeRun, **fields: Any):
        from content.models import ContentPackage
        if run.status != "SUCCEEDED":
            raise QualityBlocked([run.error or run.status])
        assets = [self.store.assets.get(item) for item in run.asset_ids]
        paths = tuple(item.path for item in assets if item)
        now = utcnow()
        return ContentPackage(
            package_id=str(fields.get("package_id") or f"pkg-{run.run_id[:8]}"),
            title=str(fields.get("title") or run.inputs.get("brief") or "Untitled"),
            body=str(fields.get("body") or run.inputs.get("brief") or ""),
            content_type=str(fields.get("content_type") or "short"),
            format=str(fields.get("format") or "short"),
            media_assets=paths,
            commerce_intent=str(run.inputs.get("commerce_intent") or "none"),
            created_at=now,
            updated_at=now,
            metadata={
                "creative_run_id": run.run_id,
                "workflow_id": run.workflow_id,
                "workflow_version": run.workflow_version,
            },
        )


def _plain_node(result: dict[str, Any]) -> dict[str, Any]:
    payload = {}
    for key, value in result.items():
        if key == "ranked":
            continue
        payload[key] = to_plain(value)
    return payload
