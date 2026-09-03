from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from creative.errors import InvalidStateTransition, WorkflowInvalid
from creative.assets import AssetStore
from creative.providers.mock import MockGenerationProvider
from creative.providers.resolver import GenerationProviderResolver
from creative.runtime.container import CreativeRuntime
from creative.runtime.state import apply_block, transition
from creative.schemas import CreativeRun, CreativeWorkflow, WorkflowEdge, WorkflowNode
from creative.store import CreativeStore, sqlite_engine
from creative.validation import validate_workflow
from creative.workflow.engine import CreativeWorkflowEngine
from creative.workflow.registry import register_workflow, resolve_workflow
from services.workers.creative_worker import run_once


def _engine(tmp_path, *, polls=0, allow_mock=True, db=None, lease_seconds=30):
    assets = AssetStore(root=tmp_path / "assets")
    store = CreativeStore(assets=assets, engine=sqlite_engine(db) if db else None, lease_seconds=lease_seconds)
    mock = MockGenerationProvider(store=assets, polls_until_done=polls)
    resolver = GenerationProviderResolver(providers={"mock": mock, "lechuang": mock}, allow_mock=allow_mock)
    return CreativeWorkflowEngine(store=store, resolver=resolver, allow_mock=allow_mock)


def test_invalid_transition_raises():
    run = CreativeRun("r", "w", "1", status="SUCCEEDED")
    with pytest.raises(InvalidStateTransition):
        transition(run, "RUNNING")


def test_blocked_reason_is_structured():
    run = CreativeRun("r", "w", "1")
    apply_block(run, "PROVIDER_AUTH_MISSING", "XIAOLEAI_API_KEY missing", retryable=False)
    assert run.status == "BLOCKED"
    assert run.blocked_reason == "PROVIDER_AUTH_MISSING"
    assert run.blocked_message
    assert run.blocked_at
    assert run.retryable is False


def test_cycle_workflow_blocks(tmp_path):
    engine = _engine(tmp_path)
    workflow = CreativeWorkflow(
        workflow_id="cycle",
        name="cycle",
        description="",
        version="1.0.0",
        category="video",
        inputs={"brief": {"required": True}},
        nodes=(WorkflowNode("a", "prompt"), WorkflowNode("b", "prompt")),
        edges=(WorkflowEdge("a", "output", "b", "input"), WorkflowEdge("b", "output", "a", "input")),
    )
    run = engine.execute(inputs={"brief": "x", "budget": 40}, workflow=workflow)
    assert run.status == "BLOCKED"
    assert run.blocked_reason == "INVALID_WORKFLOW"
    assert engine.store.list_tasks(run.run_id) == []


def test_missing_provider_credential_blocks(tmp_path, monkeypatch):
    monkeypatch.delenv("XIAOLEAI_API_KEY", raising=False)
    from creative.providers.lechuang.adapter import LechuangAdapter
    from creative.providers.lechuang.client import LechuangClient
    assets = AssetStore(root=tmp_path / "assets")
    store = CreativeStore(assets=assets)
    adapter = LechuangAdapter(client=LechuangClient(base_url="", api_key=""))
    resolver = GenerationProviderResolver(providers={"lechuang": adapter}, allow_mock=False)
    from creative.providers.judge.resolver import VisionJudgeResolver
    engine = CreativeWorkflowEngine(store=store, resolver=resolver, allow_mock=False, judge_resolver=VisionJudgeResolver(allow_mock=False, providers={}))
    run = engine.execute("creator-lifestyle-v1", {"brief": "no key", "variant_count": 1, "budget": 40})
    assert run.status == "BLOCKED"
    assert run.blocked_reason in {"PROVIDER_AUTH_MISSING", "PROVIDER_UNAVAILABLE", "PROVIDER_CONTRACT_UNVERIFIED", "CAPABILITY_UNAVAILABLE"}
    assert engine.store.list_tasks(run.run_id) == []


def test_lease_contention_exactly_one_owner(tmp_path):
    engine = _engine(tmp_path, polls=4)
    run = engine.execute("creator-lifestyle-v1", {"brief": "lease-race", "variant_count": 1, "budget": 40})
    assert run.status == "WAITING_PROVIDER"
    results = []

    def claim(name):
        results.append(engine.store.acquire_lease(run.run_id, name))

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(claim, ["worker-a", "worker-b", "worker-c"]))
    assert results.count(True) == 1
    assert results.count(False) == 2


def test_lease_expiry_allows_recovery(tmp_path):
    engine = _engine(tmp_path, lease_seconds=1)
    run = engine.execute("creator-lifestyle-v1", {"brief": "expire", "variant_count": 1, "budget": 40})
    assert engine.store.acquire_lease(run.run_id, "worker-a", seconds=0)
    from datetime import datetime, timezone
    from scripts.db.models import CreativeRunRecord
    with engine.store._session() as session:
        row = session.get(CreativeRunRecord, run.run_id)
        row.lease_until = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=5)
        session.commit()
    assert engine.store.acquire_lease(run.run_id, "worker-b") is True


def test_duplicate_provider_request_reuses_task(tmp_path):
    db = f"sqlite:///{tmp_path}/creative.db"
    engine = _engine(tmp_path, polls=2, db=db)
    run = engine.execute("creator-lifestyle-v1", {"brief": "dup-task", "variant_count": 1, "budget": 40})
    first = [item.provider_task_id for item in engine.store.list_tasks(run.run_id)]
    restarted = _engine(tmp_path, polls=2, db=db)
    restarted.resume(run.run_id)
    second = [item.provider_task_id for item in restarted.store.list_tasks(run.run_id)]
    assert first
    assert set(first) <= set(second)


def test_node_outputs_are_references(tmp_path):
    engine = _engine(tmp_path)
    run = engine.execute("creator-lifestyle-v1", {"brief": "refs", "variant_count": 1, "budget": 40})
    assert run.status == "SUCCEEDED", run.error
    for payload in run.node_outputs.values():
        assert "asset_ids" in payload
        assert "MediaAsset" not in str(payload)
        if payload.get("asset"):
            raise AssertionError("node output stored a full asset object")


def test_asset_gc_keeps_referenced_bytes(tmp_path):
    engine = _engine(tmp_path)
    run = engine.execute("creator-lifestyle-v1", {"brief": "gc", "variant_count": 1, "budget": 40})
    asset_id = run.asset_ids[0]
    assert engine.store.delete_asset(asset_id) is False
    refs = engine.store.list_asset_references(asset_id)
    assert refs["runs"]


def test_workflow_version_immutable():
    base = resolve_workflow("creator-lifestyle-v1")
    with pytest.raises(WorkflowInvalid):
        register_workflow(type(base)(**{**base.__dict__, "description": "mutated in place"}))


def test_runtime_container_owns_engine(tmp_path):
    runtime = CreativeRuntime.testing(assets=AssetStore(root=tmp_path / "assets"))
    assert runtime.engine.store is runtime.store
    assert runtime.cost_engine.store is runtime.store
    run = runtime.engine.execute("creator-lifestyle-v1", {"brief": "container", "variant_count": 1, "budget": 40})
    assert run.status in {"SUCCEEDED", "WAITING_PROVIDER", "BLOCKED"}


def test_policy_gate_blocks_hard_sell(tmp_path):
    engine = _engine(tmp_path)
    run = engine.execute("creator-lifestyle-v1", {"brief": "buy now limited time discount shop now", "variant_count": 1, "budget": 40, "commerce_intent": "product"})
    assert run.status == "BLOCKED"
    assert run.blocked_reason in {"POLICY_REJECTED", "QUALITY_FAILED"}


def test_worker_skips_without_lease(tmp_path):
    engine = _engine(tmp_path, polls=3)
    run = engine.execute("creator-lifestyle-v1", {"brief": "owned", "variant_count": 1, "budget": 40})
    assert engine.store.acquire_lease(run.run_id, "owner-1")
    skipped = run_once(engine=engine, worker_id="owner-2")
    assert run.run_id not in skipped


def test_invalid_input_blocks(tmp_path):
    engine = _engine(tmp_path)
    run = engine.execute("creator-lifestyle-v1", {"variant_count": 1, "budget": 40})
    assert run.status == "BLOCKED"
    assert run.blocked_reason == "INVALID_INPUT"
    assert engine.store.list_tasks(run.run_id) == []


def test_worker_crash_recovery(tmp_path):
    engine = _engine(tmp_path, polls=2, lease_seconds=1)
    run = engine.execute("creator-lifestyle-v1", {"brief": "crash", "variant_count": 1, "budget": 40})
    assert run.status == "WAITING_PROVIDER"
    assert engine.store.acquire_lease(run.run_id, "crashed-worker", seconds=0)
    from scripts.db.models import CreativeRunRecord
    with engine.store._session() as session:
        row = session.get(CreativeRunRecord, run.run_id)
        row.lease_until = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=5)
        session.commit()
    recovered = run_once(engine=engine, worker_id="survivor")
    assert run.run_id in recovered


def test_node_registry_owns_contracts():
    from creative.schemas import NODES, NODE_STATUS_BLOCKED
    image = NODES.require("image.generate")
    assert image["input_schema"]["prompt"] == "str"
    assert image["async"] is True
    assert "image_generation" in image["required_capabilities"]
    video = NODES.get("video.from_image")
    assert "image_to_video" in video["required_capabilities"]
    blocked = NODES.get("audio")
    assert blocked["status"] == NODE_STATUS_BLOCKED


def test_cost_engine_records_per_call(tmp_path):
    from creative.cost import CostEngine
    from creative.schemas import GenerationUsage
    engine = _engine(tmp_path)
    run = engine.execute("creator-lifestyle-v1", {"brief": "cost", "variant_count": 1, "budget": 40})
    assert run.status in {"SUCCEEDED", "WAITING_PROVIDER", "BLOCKED"}
    CostEngine(engine.store).record(GenerationUsage(
        usage_id="usage-test",
        provider="mock",
        model="mock",
        task="generate_image",
        input={"prompt": "cost"},
        output={},
        credits_estimated=1,
        credits_actual=1,
        status="SUCCEEDED",
        timestamp="2026-01-01T00:00:00+00:00",
        run_id=run.run_id,
        node_id="image",
        input_units=1,
        output_units=1,
        duration_ms=12,
        estimated_cost=1,
        actual_cost=1,
    ))
