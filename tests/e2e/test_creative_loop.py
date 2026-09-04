from agents.content.runtime import ContentAgent
from agents.media.runtime import MediaAgent
from agents.strategy.runtime import StrategyAgent
from creative.assets import AssetStore
from creative.providers.mock import MockGenerationProvider
from creative.providers.resolver import GenerationProviderResolver
from creative.workflow.engine import CreativeStore, CreativeWorkflowEngine


def test_brief_to_package_mock_loop(tmp_path):
    assets = AssetStore(root=tmp_path / "assets")
    store = CreativeStore(assets=assets)
    mock = MockGenerationProvider(store=assets)
    engine = CreativeWorkflowEngine(
        store=store,
        resolver=GenerationProviderResolver(providers={"mock": mock, "lechuang": mock, "xai": mock}, allow_mock=True),
        allow_mock=True,
    )
    strategy = StrategyAgent().run({
        "objective": "natural lifestyle",
        "audience": "young women",
        "brief": "帮我做一个15秒自然生活方式的视频，9:16，年轻女性视角，不要明显广告感。",
        "duration_seconds": 15,
        "aspect_ratio": "9:16",
        "face_visible": False,
        "style": "natural lifestyle",
        "commerce_intent": "none",
        "account_id": "acc-test",
    })
    content = ContentAgent().run({
        "title": "Morning light",
        "body": strategy["creative_requirement"]["brief"],
        "format": "short",
        "strategy": strategy,
        "commerce_intent": "none",
        "account_id": "acc-test",
        "memory": strategy["memory"],
    })
    media = MediaAgent(engine=engine).run({
        "creative_brief": content["creative_brief"],
        "allow_mock": True,
        "title": "Morning light",
        "body": content["package"].body,
        "account_id": "acc-test",
    })
    assert media["valid"] is True
    assert media["run"].status == "SUCCEEDED"
    assert media["package"] is not None
    assert media["package"].media_assets
    assert media["package"].commerce_intent == "none"
    assert media["package"].metadata["workflow_id"] in {"creator-lifestyle-v1", "creator-image-to-video-v1"}
