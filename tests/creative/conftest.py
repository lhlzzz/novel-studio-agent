import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
for name in list(sys.modules):
    if name == "creative" or name.startswith("creative."):
        # tests/creative must not shadow the product package
        if getattr(sys.modules[name], "__file__", "") and "tests/creative" in str(getattr(sys.modules[name], "__file__", "")):
            del sys.modules[name]

import pytest

from creative.assets import AssetStore
from creative.providers.mock import MockGenerationProvider
from creative.providers.resolver import GenerationProviderResolver
from creative.workflow.engine import CreativeStore, CreativeWorkflowEngine


@pytest.fixture
def engine(tmp_path: Path) -> CreativeWorkflowEngine:
    assets = AssetStore(root=tmp_path / "assets")
    store = CreativeStore(assets=assets)
    mock = MockGenerationProvider(store=assets)
    resolver = GenerationProviderResolver(providers={"mock": mock, "lechuang": mock}, allow_mock=True)
    return CreativeWorkflowEngine(store=store, resolver=resolver, allow_mock=True)
