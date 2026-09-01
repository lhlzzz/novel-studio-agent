from pathlib import Path

import pytest

from creative.assets import MIN_PNG, AssetStore, persist_bytes
from creative.errors import JudgeBlocked, WorkflowInvalid
from creative.providers.mock import MockGenerationProvider
from creative.providers.resolver import GenerationProviderResolver, ProviderRanker, ModelCapability
from creative.schemas import CreativeWorkflow, MediaAsset, WorkflowEdge, WorkflowNode
from creative.store import CreativeStore, sqlite_engine
from creative.validation import validate_workflow
from creative.workflow.engine import CreativeWorkflowEngine
from creative.workflow.registry import resolve_workflow
from services.workers.creative_worker import run_once


def _engine(tmp_path, *, polls=0, allow_mock=True, db=None, judge=None):
    assets = AssetStore(root=tmp_path / "assets")
    store = CreativeStore(assets=assets, engine=sqlite_engine(db) if db else None)
    mock = MockGenerationProvider(store=assets, polls_until_done=polls)
    resolver = GenerationProviderResolver(providers={"mock": mock, "lechuang": mock}, allow_mock=allow_mock)
    kwargs = {}
    if judge is not None:
        kwargs["judge_resolver"] = judge
    return CreativeWorkflowEngine(store=store, resolver=resolver, allow_mock=allow_mock, **kwargs)


def test_persistence_roundtrip(tmp_path):
    engine = _engine(tmp_path)
    run = engine.execute("creator-image-to-video-v1", {"brief": "persist", "variant_count": 1, "budget": 40})
    loaded = engine.store.get_run(run.run_id)
    assert loaded is not None
    assert loaded.node_outputs
    assert engine.store.list_assets(run.run_id)


def test_restart_recovery(tmp_path):
    db = f"sqlite:///{tmp_path}/creative.db"
    engine = _engine(tmp_path, polls=2, db=db)
    run = engine.execute("creator-image-to-video-v1", {"brief": "restart", "variant_count": 1, "budget": 40})
    assert run.status == "WAITING_PROVIDER"
    provider_ids = {task.provider_task_id for task in engine.store.list_open_tasks(run.run_id)}
    assert provider_ids
    restarted = _engine(tmp_path, polls=2, db=db)
    for _ in range(6):
        run_once(engine=restarted)
        run = restarted.store.get_run(run.run_id)
        if run.status == "SUCCEEDED":
            break
    assert run.status == "SUCCEEDED", run.error
    after = {task.provider_task_id for task in restarted.store.list_tasks(run.run_id)}
    assert provider_ids <= after


def test_duplicate_worker_lease(tmp_path):
    engine = _engine(tmp_path)
    run = engine.execute("creator-image-to-video-v1", {"brief": "lease", "variant_count": 1, "budget": 40})
    assert engine.store.acquire_lease(run.run_id, "worker-a")
    assert engine.store.acquire_lease(run.run_id, "worker-a")
    assert engine.store.acquire_lease(run.run_id, "worker-b") is False


def test_provider_crash_reuses_provider_task(tmp_path):
    db = f"sqlite:///{tmp_path}/creative.db"
    engine = _engine(tmp_path, polls=3, db=db)
    run = engine.execute("creator-image-to-video-v1", {"brief": "crash", "variant_count": 1, "budget": 40})
    tasks = engine.store.list_open_tasks(run.run_id)
    assert tasks
    original = tasks[0].provider_task_id
    restarted = _engine(tmp_path, polls=3, db=db)
    restarted.resume(run.run_id)
    again = restarted.store.list_tasks(run.run_id)
    assert original in {item.provider_task_id for item in again}
    assert all(item.provider_task_id != "" for item in again)


def test_judge_unavailable_blocks(tmp_path):
    from creative.providers.judge.resolver import VisionJudgeResolver
    engine = _engine(tmp_path, allow_mock=False, judge=VisionJudgeResolver(allow_mock=False, providers={}))
    run = engine.execute("creator-image-to-video-v1", {"brief": "no judge", "variant_count": 1, "budget": 40})
    assert run.status == "BLOCKED"
    assert run.error_code in {"QUALITY_FAILED", "JUDGE_UNAVAILABLE", "judge_blocked"} or "judge" in (run.error or "").lower()


def test_render_failure_does_not_fake_asset(tmp_path, monkeypatch):
    from creative.errors import TechnicalMediaError
    from creative.render import pipeline
    engine = _engine(tmp_path)
    def boom(*args, **kwargs):
        raise TechnicalMediaError("ffmpeg failed")
    monkeypatch.setattr("creative.render.render_asset", boom)
    monkeypatch.setattr("creative.render.pipeline.render_asset", boom)
    run = engine.execute("creator-image-to-video-v1", {"brief": "render fail", "variant_count": 1, "budget": 40})
    assert run.status == "FAILED"
    finals = [engine.store.assets.get(item) for item in run.asset_ids if (engine.store.assets.get(item) or type("X", (), {"type": ""})()).type == "final"]
    assert not finals


def test_budget_never_creates_provider_task(tmp_path):
    engine = _engine(tmp_path)
    run = engine.execute("creator-image-to-video-v1", {"brief": "broke", "variant_count": 4, "budget": 1})
    assert run.status == "BLOCKED"
    assert engine.store.list_tasks(run.run_id) == []


def test_unverified_capability_blocks(tmp_path):
    class Dead:
        name = "dead"
        supported = frozenset()
        verified_capabilities = frozenset()
        def has_verified(self, capability):
            return False
        def live_ready(self):
            return True, "ok"
        def create_task(self, kind, payload):
            raise AssertionError("provider task must not be created")
        def estimate(self, kind, payload=None):
            return 1.0
    assets = AssetStore(root=tmp_path / "assets")
    store = CreativeStore(assets=assets)
    resolver = GenerationProviderResolver(providers={"lechuang": Dead(), "mock": Dead()}, allow_mock=False)
    from creative.providers.judge.mock import MockVisionJudgeProvider
    from creative.providers.judge.resolver import VisionJudgeResolver
    engine = CreativeWorkflowEngine(
        store=store,
        resolver=resolver,
        allow_mock=False,
        judge_resolver=VisionJudgeResolver(providers={"mock-vision": MockVisionJudgeProvider()}, allow_mock=True),
    )
    run = engine.execute("creator-image-to-video-v1", {"brief": "blocked capability", "variant_count": 1, "budget": 40})
    assert run.status == "BLOCKED"
    assert engine.store.list_tasks(run.run_id) == []


def test_workflow_validation_cycle_and_unknown():
    cycle = CreativeWorkflow(
        workflow_id="cycle",
        name="cycle",
        description="",
        version="1.0.0",
        category="video",
        inputs={"brief": {"required": True}},
        nodes=(WorkflowNode("a", "prompt"), WorkflowNode("b", "prompt")),
        edges=(WorkflowEdge("a", "output", "b", "input"), WorkflowEdge("b", "output", "a", "input")),
    )
    with pytest.raises(WorkflowInvalid):
        validate_workflow(cycle, {"brief": "x"})
    bad_edge = CreativeWorkflow(
        workflow_id="edge",
        name="edge",
        description="",
        version="1.0.0",
        category="video",
        inputs={},
        nodes=(WorkflowNode("a", "input"),),
        edges=(WorkflowEdge("a", "output", "missing", "input"),),
    )
    with pytest.raises(WorkflowInvalid):
        validate_workflow(bad_edge, {})


def test_workflow_validation_blocks_run(tmp_path):
    engine = _engine(tmp_path)
    workflow = CreativeWorkflow(
        workflow_id="bad",
        name="bad",
        description="",
        version="1.0.0",
        category="video",
        inputs={"brief": {"required": True}},
        nodes=(WorkflowNode("a", "prompt"), WorkflowNode("b", "prompt")),
        edges=(WorkflowEdge("a", "output", "b", "input"), WorkflowEdge("b", "output", "a", "input")),
    )
    run = engine.execute(inputs={"brief": "x", "budget": 40}, workflow=workflow)
    assert run.status == "BLOCKED"
    assert run.error_code in {"WORKFLOW_INVALID", "INVALID_WORKFLOW"}


def test_asset_content_address(tmp_path):
    store = AssetStore(root=tmp_path)
    first = store.save_generated(MIN_PNG, asset_type="image", suffix=".png", mime_type="image/png", width=1, height=1)
    second = store.save_generated(MIN_PNG, asset_type="image", suffix=".png", mime_type="image/png", width=1, height=1)
    assert first.sha256 == second.sha256 == first.asset_id


def test_replay_points_at_old_run(tmp_path):
    engine = _engine(tmp_path)
    first = engine.execute("creator-lifestyle-v1", {"brief": "replay me", "variant_count": 1, "budget": 40})
    replay = engine.replay(first.run_id)
    assert replay.run_id != first.run_id
    assert replay.replay_of == first.run_id
    assert engine.store.get_run(first.run_id).status == first.status


def test_local_image_nodes(tmp_path):
    engine = _engine(tmp_path)
    image = persist_bytes(MIN_PNG * 20 + b"pad-bytes-for-unique", asset_type="image", suffix=".png", root=tmp_path / "assets", mime_type="image/png", width=64, height=64)
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (64, 80), (10, 20, 30)).save(buf, format="PNG")
    asset = engine.store.assets.save_generated(buf.getvalue(), asset_type="image", suffix=".png", mime_type="image/png", width=64, height=80)
    from creative.nodes import execute_node
    from creative.schemas import CreativeRun, CreativeWorkflow, WorkflowNode
    workflow = CreativeWorkflow("w", "n", "", "1", "x", {}, (WorkflowNode("crop", "image_crop"),), ())
    run = CreativeRun("r", "w", "1", inputs={})
    cropped = execute_node(WorkflowNode("crop", "image_crop", config={"aspect_ratio": "1:1"}, inputs={"asset": asset}), workflow=workflow, run=run, context={}, store=engine.store, resolver=engine.resolver)
    assert cropped["asset"].width == cropped["asset"].height
    node = WorkflowNode("split", "image_split", config={"rows": 1, "columns": 2}, inputs={"asset": asset})
    split = execute_node(node, workflow=workflow, run=run, context={}, store=engine.store, resolver=engine.resolver)
    assert len(split["tiles"]) == 2
    annotated = execute_node(WorkflowNode("ann", "image_annotate", inputs={"asset": asset, "label": "look", "instruction": "pan"}), workflow=workflow, run=run, context={}, store=engine.store, resolver=engine.resolver)
    assert Path(annotated["asset"].path).is_file()


def test_cost_quote_and_ranker():
    ranker = ProviderRanker()
    matches = [
        ModelCapability("lechuang", "a", ("text",), ("image",), (), (), ("9:16",), (), True, False, ("text_to_image",)),
        ModelCapability("lechuang", "b", ("text",), ("image",), (), (), ("9:16",), (), True, True, ("text_to_image",)),
    ]
    ranked = ranker.rank(matches, requirement={"capability": "text_to_image"})
    assert ranked[0].verified is True


def test_storyboard_multiple_shots(tmp_path):
    engine = _engine(tmp_path)
    from creative.nodes import execute_node
    from creative.schemas import CreativeRun, CreativeWorkflow, WorkflowNode
    workflow = CreativeWorkflow("w", "n", "", "1", "x", {}, (WorkflowNode("board", "storyboard"),), ())
    run = CreativeRun("r", "w", "1", inputs={"brief": "one. two. three.", "duration_seconds": 9})
    result = execute_node(WorkflowNode("board", "storyboard"), workflow=workflow, run=run, context={}, store=engine.store, resolver=engine.resolver)
    assert len(result["shots"]) >= 3


def test_api_and_idempotency(tmp_path):
    from creative.api import CreativeAPI
    engine = _engine(tmp_path)
    api = CreativeAPI(engine)
    first = api.create_run("creator-lifestyle-v1", {"brief": "api", "variant_count": 1, "budget": 40})
    second = api.create_run("creator-lifestyle-v1", {"brief": "api", "variant_count": 1, "budget": 40})
    assert first.run_id == second.run_id
    assert api.get_run(first.run_id).run_id == first.run_id
    assert api.list_assets(first.run_id)
