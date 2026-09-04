"""CreativeWorkflowEngine is the sole generation owner. Agents select; this executes."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from creative.assets import AssetStore
from creative.errors import (
    BudgetExceeded,
    IllegalRunTransition,
    InvalidStateTransition,
    JudgeBlocked,
    PolicyRejected,
    ProviderBlocked,
    QualityBlocked,
    TechnicalMediaError,
    WorkflowInvalid,
    failure_code,
    user_message,
)
from creative.judges import RegenerationStrategy
from creative.nodes import estimate_workflow_cost, execute_node, quality_gate
from creative.idempotency import IdempotencyKey
from creative.runtime.state import apply_block, block_reason_for, transition as state_transition
from creative.providers.judge.resolver import VisionJudgeResolver
from creative.providers.resolver import GenerationProviderResolver
from creative.schemas import RUN_TRANSITIONS, CreativeRun, CreativeWorkflow, MediaAsset, map_task_status, to_plain, utcnow
from creative.store import CreativeStore
from creative.validation import topo_sort, validate_workflow
from creative.workflow.registry import resolve_workflow, workflow_from_dict
from creative.workflow.resolver import resolve_from_requirement
from governance.observability import log_event, new_request_id


def make_idempotency_key(workflow_id: str, version: str, inputs: dict[str, Any]) -> str:
    return IdempotencyKey.run(workflow_id, version, inputs)


def transition(run: CreativeRun, status: str) -> CreativeRun:
    return state_transition(run, status)


def workflow_from_snapshot(snapshot: dict[str, Any] | None, fallback_id: str, fallback_version: str) -> CreativeWorkflow:
    if snapshot:
        return workflow_from_dict(snapshot)
    return resolve_workflow(fallback_id, fallback_version)


class CreativeWorkflowEngine:
    def __init__(
        self,
        *,
        store: CreativeStore | None = None,
        resolver: GenerationProviderResolver | None = None,
        allow_mock: bool = False,
        worker_id: str | None = None,
        judge_resolver: VisionJudgeResolver | None = None,
    ) -> None:
        self.store = store or CreativeStore()
        self.allow_mock = allow_mock
        self.worker_id = worker_id or f"engine-{uuid4().hex[:8]}"
        self.resolver = resolver or GenerationProviderResolver(allow_mock=allow_mock)
        self.judge_resolver = judge_resolver or VisionJudgeResolver(allow_mock=allow_mock)
        if allow_mock:
            from creative.providers.mock import MockGenerationProvider
            mock = self.resolver.providers.get("mock") or MockGenerationProvider(store=self.store.assets)
            if getattr(mock, "store", None) is not self.store.assets:
                mock = MockGenerationProvider(
                    store=self.store.assets,
                    polls_until_done=getattr(mock, "polls_until_done", 0),
                )
                self.resolver.providers["mock"] = mock
            if self.allow_mock:
                if getattr(self.resolver.providers.get("lechuang"), "name", "") != "mock":
                    self.resolver.providers["lechuang"] = mock
                if getattr(self.resolver.providers.get("xai"), "name", "") != "mock":
                    self.resolver.providers["xai"] = mock

    @classmethod
    def production(cls, **kwargs: Any) -> "CreativeWorkflowEngine":
        return cls(store=CreativeStore.production(), allow_mock=False, **kwargs)

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
        workflow: CreativeWorkflow | None = None,
    ) -> CreativeRun:
        if allow_mock is not None:
            self.allow_mock = allow_mock
            self.resolver.allow_mock = allow_mock
            self.judge_resolver.allow_mock = allow_mock
        payload = dict(requirement or {})
        payload.update(inputs or {})
        if workflow is None:
            workflow = resolve_workflow(workflow_id) if workflow_id else self.select(payload)
        key = None if replay_of else (idempotency_key or make_idempotency_key(workflow.workflow_id, workflow.version, payload))
        if key:
            existing = self.store.get_by_idempotency(key)
            if existing is not None:
                return existing
        try:
            validate_workflow(workflow, payload)
        except WorkflowInvalid as exc:
            run = CreativeRun(
                run_id=uuid4().hex,
                workflow_id=workflow.workflow_id,
                workflow_version=workflow.version,
                inputs=payload,
                budget=float(budget if budget is not None else payload.get("budget") or 40),
                idempotency_key=key,
                workflow_snapshot=workflow.export(),
                replay_of=replay_of,
                request_id=new_request_id(),
            )
            reasons = getattr(exc, "reasons", ()) or (str(exc),)
            block = "INVALID_INPUT" if any("missing input" in str(item) for item in reasons) else "INVALID_WORKFLOW"
            apply_block(run, block, user_message(exc), retryable=False)
            self.store.save_run(run)
            self.store.record_event(run.run_id, "run_blocked", {"error": run.error, "code": run.error_code, "reason": run.blocked_reason})
            return run
        run = CreativeRun(
            run_id=uuid4().hex,
            workflow_id=workflow.workflow_id,
            workflow_version=workflow.version,
            inputs=payload,
            budget=float(budget if budget is not None else payload.get("budget") or 40),
            idempotency_key=key,
            workflow_snapshot=workflow.export(),
            replay_of=replay_of,
            request_id=new_request_id(),
        )
        run.estimated_cost = estimate_workflow_cost(workflow, payload, resolver=self.resolver)
        self.store.save_run(run)
        self.store.save_workflow_snapshot(run.workflow_snapshot)
        self.store.record_event(run.run_id, "run_created", {"workflow_id": workflow.workflow_id, "version": workflow.version})
        log_event(agent="creative-engine", action="create_run", status="created", request_id=run.request_id or "", run_id=run.run_id, provider="", duration_ms=None)
        if run.budget is not None and run.estimated_cost > float(run.budget):
            apply_block(run, "BUDGET_EXCEEDED", f"estimated cost {run.estimated_cost} exceeds budget {run.budget}", retryable=False)
            self.store.save_run(run)
            self.store.record_event(run.run_id, "run_blocked", {"error": run.error, "reason": run.blocked_reason})
            return run
        try:
            transition(run, "QUEUED")
            self.store.save_run(run)
            transition(run, "RUNNING")
            self.store.save_run(run)
            return self._advance(run, workflow)
        except Exception as exc:
            return self._fail(run, exc)

    def replay(self, run_id: str, *, allow_mock: bool | None = None) -> CreativeRun:
        previous = self.store.get_run(run_id)
        if previous is None:
            raise KeyError(run_id)
        workflow = workflow_from_snapshot(previous.workflow_snapshot, previous.workflow_id, previous.workflow_version)
        return self.execute(
            previous.workflow_id,
            dict(previous.inputs),
            replay_of=run_id,
            budget=previous.budget,
            allow_mock=self.allow_mock if allow_mock is None else allow_mock,
            workflow=workflow,
        )

    def resume(self, run_id: str, *, worker_id: str | None = None) -> CreativeRun:
        run = self.store.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        worker = worker_id or self.worker_id
        if not self.store.acquire_lease(run.run_id, worker):
            return run
        run = self.store.get_run(run_id) or run
        workflow = workflow_from_snapshot(run.workflow_snapshot, run.workflow_id, run.workflow_version)
        self._poll_open_tasks(run)
        run = self.store.get_run(run.run_id) or run
        if run.status == "WAITING_PROVIDER" and not self.store.list_open_tasks(run.run_id):
            transition(run, "RUNNING")
            self.store.save_run(run)
        if run.status != "RUNNING":
            return run
        try:
            return self._advance(run, workflow)
        except Exception as exc:
            return self._fail(run, exc)

    def cancel(self, run_id: str) -> CreativeRun:
        run = self.store.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        if run.status not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            transition(run, "CANCELLED")
            run.error_code = "CANCELLED"
            self.store.save_run(run)
        return run

    def _judge_provider(self):
        try:
            return self.judge_resolver.resolve()
        except (JudgeBlocked, ProviderBlocked):
            if self.allow_mock:
                from creative.providers.judge.mock import MockVisionJudgeProvider
                return MockVisionJudgeProvider()
            raise

    def _poll_open_tasks(self, run: CreativeRun) -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        self.store.heartbeat(run.run_id, self.worker_id)
        for task in self.store.list_open_tasks(run.run_id):
            self.store.heartbeat(run.run_id, self.worker_id)
            if task.timeout_at:
                from datetime import datetime as dt
                try:
                    deadline = dt.fromisoformat(task.timeout_at.replace("Z", "+00:00"))
                    if deadline.tzinfo is None:
                        deadline = deadline.replace(tzinfo=timezone.utc)
                    if now > deadline:
                        task.status = "FAILED"
                        task.error = "generation timed out"
                        self.store.save_task(task)
                        continue
                except ValueError:
                    pass
            provider, _ = self.resolver.resolve(task.provider if task.provider != "mock" else "mock")
            if task.provider in {"lechuang", "xai"} and self.allow_mock:
                provider, _ = self.resolver.resolve(task.provider)
            if task.poll_count >= 30:
                task.status = "FAILED"
                task.error = "generation timed out"
                self.store.save_task(task)
                continue
            handle = provider.get_task(task.provider_task_id)
            task.poll_count = handle.poll_count
            task.status = map_task_status(handle.status)
            task.result = dict(handle.result or {})
            task.error = handle.error
            if task.status == "SUCCEEDED":
                task.completed_at = utcnow()
                asset = handle.result.get("asset")
                if isinstance(asset, MediaAsset):
                    stored = self.store.assets.put(asset)
                    if stored.asset_id not in run.asset_ids:
                        run.asset_ids.append(stored.asset_id)
                    node_out = run.node_outputs.setdefault(task.node_id, {"asset_ids": [], "character_ids": [], "prompt_ids": [], "judge_run_ids": []})
                    ids = node_out.setdefault("asset_ids", [])
                    if stored.asset_id not in ids:
                        ids.append(stored.asset_id)
                self.store.record_event(run.run_id, "provider_completed", {"task_id": task.task_id, "status": task.status})
            self.store.save_task(task)
        self.store.save_run(run)

    def _advance(self, run: CreativeRun, workflow: CreativeWorkflow) -> CreativeRun:
        order, cycle = topo_sort(workflow)
        if cycle:
            raise WorkflowInvalid("cycle")
        context = _hydrate_context(run, self.store)
        regen = RegenerationStrategy()
        max_regens = int(workflow.quality_policy.get("max_regenerations") or 2)
        while run.cursor < len(order):
            node = order[run.cursor]
            self.store.heartbeat(run.run_id, self.worker_id)
            self.store.record_event(run.run_id, "node_started", {"node_id": node.node_id, "type": node.type})
            open_for_node = [item for item in self.store.list_open_tasks(run.run_id) if item.node_id == node.node_id]
            existing = context.get(node.node_id) or {}
            if open_for_node:
                transition(run, "WAITING_PROVIDER")
                self.store.save_run(run)
                return run
            if node.type in {"image_generate", "image.generate", "video_generate", "video.generate", "video.from_image", "image_edit", "image.transform", "video_edit", "video_extend", "multi_angle"} and (existing.get("asset_ids") or existing.get("asset") or existing.get("output")):
                run.cursor += 1
                self.store.save_run(run)
                continue
            if existing.get("output") is not None and node.type not in {"image_generate", "image.generate", "video_generate", "video.generate", "video.from_image", "image_edit", "image.transform", "video_edit", "video_extend", "multi_angle", "judge", "render"}:
                run.cursor += 1
                self.store.save_run(run)
                continue
            if node.type in {"judge", "image_analyze"} and run.status == "RUNNING":
                transition(run, "JUDGING")
                self.store.save_run(run)
            result = execute_node(
                node,
                workflow=workflow,
                run=run,
                context=context,
                store=self.store,
                resolver=self.resolver,
                judge_provider=self._judge_provider() if node.type in {"judge", "image_analyze"} else None,
            )
            if result.get("_pending"):
                run.node_outputs[node.node_id] = _node_refs(result)
                self.store.save_node_output(run.run_id, node.node_id, run.node_outputs[node.node_id])
                transition(run, "WAITING_PROVIDER")
                self.store.save_run(run)
                return run
            if node.type == "judge" and result.get("decision") == "FAIL":
                attempt = int((run.outputs.get("regen_attempt") or 0))
                action = regen.next_action(attempt, max_regenerations=max_regens)
                run.outputs["regen_attempt"] = attempt + 1
                if action == "stop":
                    run.error = "quality gate blocked: regeneration budget exceeded"
                    run.error_code = "QUALITY_FAILED"
                    context[node.node_id] = result
                    run.node_outputs[node.node_id] = _plain_node(result)
                    break
                generate_index = max((index for index, item in enumerate(order[: run.cursor]) if item.type in {"image_generate", "video_generate", "multi_angle"}), default=None)
                if generate_index is not None:
                    run.cursor = generate_index
                    run.inputs = _apply_regen(run.inputs, action)
                    for item in order[generate_index: run.cursor + 1]:
                        run.node_outputs.pop(item.node_id, None)
                    context = _hydrate_context(run, self.store)
                    if run.status == "JUDGING":
                        transition(run, "RUNNING")
                    self.store.save_run(run)
                    continue
            context[node.node_id] = result
            run.node_outputs[node.node_id] = _node_refs(result)
            self.store.save_node_output(run.run_id, node.node_id, run.node_outputs[node.node_id], result.get("assets") or ([result["asset"]] if result.get("asset") else []))
            if run.status == "JUDGING":
                transition(run, "RUNNING")
            run.cursor += 1
            self.store.save_run(run)
            self.store.record_event(run.run_id, "node_completed", {"node_id": node.node_id, "type": node.type})
        final = None
        for node in reversed(order):
            payload = context.get(node.node_id) or run.node_outputs.get(node.node_id) or {}
            candidate = payload.get("asset") or payload.get("output")
            if isinstance(candidate, MediaAsset):
                final = candidate
                break
            if isinstance(candidate, dict) and candidate.get("asset_id"):
                final = self.store.get_asset(candidate["asset_id"]) or self.store.assets.get(candidate["asset_id"])
                if final:
                    break
        assets = [self.store.get_asset(item) or self.store.assets.get(item) for item in run.asset_ids]
        assets = [item for item in assets if item]
        gate = quality_gate(run, assets)
        run.quality = {key: str(value) for key, value in gate.items() if key not in {"reasons", "technical_score", "visual_score", "content_score", "platform_score", "overall_score"}}
        run.selected_asset_id = run.selected_asset_id or (final.asset_id if final else None)
        run.outputs = {
            "asset_id": final.asset_id if final else run.selected_asset_id,
            "assets": [item.asset_id for item in assets],
            "quality": run.quality,
            "estimated_cost": run.estimated_cost,
            "actual_cost": run.actual_cost,
            "selected_asset_id": run.selected_asset_id,
            "selection_reason": run.selection_reason,
            "selection_score": run.selection_score,
            "regen_attempt": run.outputs.get("regen_attempt"),
            **{key: gate[key] for key in ("technical_score", "visual_score", "content_score", "platform_score", "overall_score") if key in gate},
        }
        required = ("visual_quality", "identity_quality", "technical_quality")
        if gate.get("policy_quality") == "fail":
            apply_block(run, "POLICY_REJECTED", run.error or ("policy blocked: " + ", ".join(gate.get("reasons") or [])), retryable=False)
            self.store.record_event(run.run_id, "run_blocked", {"error": run.error, "reason": run.blocked_reason})
        elif any(run.quality.get(key) != "pass" for key in required) or run.error_code == "QUALITY_FAILED":
            reason = "JUDGE_UNAVAILABLE" if run.quality.get("visual_quality") == "blocked" else "QUALITY_FAILED"
            apply_block(run, reason, run.error or ("quality gate blocked: " + ", ".join(gate.get("reasons") or [])), retryable=False)
            self.store.record_event(run.run_id, "run_blocked", {"error": run.error, "reason": run.blocked_reason})
        else:
            transition(run, "SUCCEEDED")
            self.store.save_performance({
                "workflow_id": run.workflow_id,
                "version": run.workflow_version,
                "run_id": run.run_id,
                "asset_id": run.selected_asset_id or "",
                "quality_score": gate.get("overall_score"),
                "cost": run.actual_cost,
                "character": run.inputs.get("character_id") or "",
                "motion": run.inputs.get("motion") or "",
                "camera": run.inputs.get("camera") or "",
                "duration": run.inputs.get("duration_seconds"),
            })
            self.store.record_event(run.run_id, "run_completed", {"asset_id": run.selected_asset_id})
        self.store.save_run(run)
        return run

    def to_content_package(self, run: CreativeRun, **fields: Any):
        from content.models import ContentPackage
        from content.platform_policy import differentiate_package
        if run.status != "SUCCEEDED":
            raise QualityBlocked([run.error or run.status])
        if any(str(run.quality.get(key) or "") != "pass" for key in ("visual_quality", "identity_quality", "technical_quality") if run.quality):
            raise QualityBlocked([run.error or "quality gate blocked"])
        assets = [self.store.get_asset(item) or self.store.assets.get(item) for item in run.asset_ids]
        paths = tuple(item.path for item in assets if item)
        now = utcnow()
        context = fields.get("creative_context") or run.inputs.get("creative_context")
        package = ContentPackage(
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
                "selected_asset_id": run.selected_asset_id,
            },
            account_id=getattr(context, "account_id", None) or run.inputs.get("account_id"),
            series_id=getattr(context, "series_id", None) or run.inputs.get("series_id"),
            episode_id=getattr(context, "episode_id", None) or run.inputs.get("episode_id"),
            platform=str(getattr(context, "platform", "") or run.inputs.get("platform") or ""),
            status="GENERATED",
            character_id=getattr(context, "character_id", None) or run.inputs.get("character_id"),
            world_id=getattr(context, "world_id", None) or run.inputs.get("world_id"),
            creative_context_id=getattr(context, "context_id", None) or run.inputs.get("creative_context_id"),
        )
        if context is not None and hasattr(context, "platform") and context.platform:
            package = differentiate_package(package, context)
        return package

    def _fail(self, run: CreativeRun, exc: Exception) -> CreativeRun:
        run.error = user_message(exc)
        run.error_code = failure_code(exc)
        blocked_types = (ProviderBlocked, BudgetExceeded, JudgeBlocked, WorkflowInvalid, QualityBlocked, PolicyRejected)
        target = "BLOCKED" if isinstance(exc, blocked_types) else "FAILED"
        if isinstance(exc, TechnicalMediaError):
            run.error_code = "TECHNICAL_MEDIA_FAILED"
            target = "FAILED"
        if target == "BLOCKED":
            apply_block(run, block_reason_for(exc), run.error, retryable=bool(getattr(exc, "retryable", False)))
        else:
            try:
                transition(run, target)
            except InvalidStateTransition:
                raise
        self.store.save_run(run)
        self.store.record_event(run.run_id, "run_blocked" if target == "BLOCKED" else "run_failed", {"error": run.error, "code": run.error_code, "reason": getattr(run, "blocked_reason", None)})
        log_event(
            agent="creative-engine",
            action="run",
            status=target.lower(),
            request_id=run.request_id or "",
            run_id=run.run_id,
            provider="",
            error_code=run.error_code,
        )
        return run


def _apply_regen(inputs: dict[str, Any], action: str) -> dict[str, Any]:
    payload = {**inputs, "regen_action": action, "variation_seed": action}
    if action == "change_camera":
        payload["camera"] = "handheld"
    if action == "change_model":
        payload["model_override"] = inputs.get("model_override") or "mock"
        payload["provider_override"] = inputs.get("provider_override") or inputs.get("provider")
    if action == "change_variation":
        payload["seed"] = int(inputs.get("seed") or 0) + 17
    if action == "change_prompt":
        payload["brief"] = f"{inputs.get('brief') or ''} regenerated framing".strip()
    if action == "change_reference" and inputs.get("reference_override"):
        payload["reference"] = inputs.get("reference_override")
    return payload


def _plain_node(result: dict[str, Any]) -> dict[str, Any]:
    return _node_refs(result)


def _ids(values) -> list[str]:
    ids = []
    if values is None:
        return ids
    if not isinstance(values, (list, tuple)):
        values = [values]
    for item in values:
        if item is None:
            continue
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict) and (item.get("asset_id") or item.get("character_id") or item.get("prompt_id") or item.get("judge_id")):
            ids.append(item.get("asset_id") or item.get("character_id") or item.get("prompt_id") or item.get("judge_id"))
        else:
            for attr in ("asset_id", "character_id", "prompt_id", "judge_id"):
                value = getattr(item, attr, None)
                if value:
                    ids.append(value)
                    break
    return list(dict.fromkeys(ids))


def _node_refs(result: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "asset_ids": _ids(result.get("assets") or result.get("asset") or result.get("variants") or result.get("output") if not isinstance(result.get("output"), str) else None),
        "character_ids": _ids(result.get("character") or result.get("character_id")),
        "prompt_ids": _ids(result.get("prompt_asset") or result.get("prompt_id")),
        "judge_run_ids": _ids(result.get("judge") or result.get("judge_id")),
    }
    if result.get("character_id"):
        payload["character_id"] = result.get("character_id")
        if result.get("character_id") not in payload["character_ids"]:
            payload["character_ids"].append(result.get("character_id"))
    if isinstance(result.get("output"), str):
        payload["output"] = result.get("output")
        payload["prompt"] = result.get("prompt") or result.get("output")
    if result.get("decision"):
        payload["decision"] = result.get("decision")
    if result.get("_pending"):
        payload["pending"] = True
    return payload



def _hydrate_context(run: CreativeRun, store) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for node_id, payload in (run.node_outputs or {}).items():
        data = dict(payload or {})
        assets = []
        for item in data.get("asset_ids") or []:
            asset = store.get_asset(item) or store.assets.get(item)
            if asset is not None:
                assets.append(asset)
        if assets:
            data["asset"] = assets[0]
            data["output"] = data.get("output") or assets[0]
            data["assets"] = assets
            data["variants"] = assets
        context[node_id] = data
    return context
