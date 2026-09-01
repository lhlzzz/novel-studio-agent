from creative.assets import AssetStore
from creative.providers.mock import MockGenerationProvider
from creative.providers.resolver import GenerationProviderResolver
from creative.workflow.engine import CreativeStore, CreativeWorkflowEngine
from services.workers.creative_worker import run_once


def test_async_generation_uses_worker(tmp_path):
    assets = AssetStore(root=tmp_path / "assets")
    store = CreativeStore(assets=assets)
    mock = MockGenerationProvider(store=assets, polls_until_done=2)
    resolver = GenerationProviderResolver(providers={"mock": mock, "lechuang": mock}, allow_mock=True)
    engine = CreativeWorkflowEngine(store=store, resolver=resolver, allow_mock=True)
    run = engine.execute("creator-image-to-video-v1", {"brief": "async", "variant_count": 1, "budget": 40})
    assert run.status == "WAITING_PROVIDER"
    assert engine.store.list_open_tasks(run.run_id)
    for _ in range(4):
        run_once(engine=engine)
        run = engine.store.get_run(run.run_id)
        if run.status == "SUCCEEDED":
            break
    assert run.status == "SUCCEEDED", run.error
