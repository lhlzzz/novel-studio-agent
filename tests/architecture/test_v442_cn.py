from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = ("agents", "social", "creative", "integrations", "scripts", "services", "governance")


def _iter_py():
    for name in PRODUCTION:
        for path in (ROOT / name).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path


def test_cn_providers_registered():
    from social.providers.resolver import ADAPTER_IMPORTS, resolve_social_provider
    for name, cls in {
        "xiaohongshu": "XiaohongshuAdapter",
        "douyin": "DouyinAdapter",
        "kuaishou": "KuaishouAdapter",
        "xianyu": "XianyuAdapter",
    }.items():
        handle = resolve_social_provider(name)
        assert handle.implementation.__class__.__name__ == cls
        assert name in ADAPTER_IMPORTS


def test_yaml_cannot_enable():
    from social.providers.registry import load_social_registry
    registry = load_social_registry()
    for name in ("xiaohongshu", "douyin", "kuaishou", "xianyu"):
        assert registry[name].enabled is False


def test_production_runtime_rejects_inmemory():
    from integrations.persistence import InMemoryStore
    from social.runtime.container import SocialRuntime
    import pytest
    with pytest.raises(ValueError):
        SocialRuntime.create(store=InMemoryStore(), secrets=__import__("social.auth.secrets", fromlist=["UnconfiguredSecretStore"]).UnconfiguredSecretStore(), production=True)


def test_production_paths_do_not_default_inmemory():
    entrypoints = {
        "scripts/meiti.py",
        "scripts/social_doctor.py",
        "scripts/meiti_doctor.py",
        "scripts/runtime_check.py",
        "services/workers/scheduler.py",
        "services/workers/reconciliation_worker.py",
        "services/workers/analytics_worker.py",
        "services/control_plane/service.py",
    }
    hits = []
    for path in _iter_py():
        rel = str(path.relative_to(ROOT))
        body = path.read_text(encoding="utf-8")
        if rel in entrypoints and "store or InMemoryStore()" in body:
            hits.append(rel)
    assert hits == []


def test_no_fake_providers_in_production():
    for path in _iter_py():
        text = path.read_text(encoding="utf-8")
        for token in ("FakeDouyin", "FakeKuaishou", "FakeXHS", "FakeXianyu", "FakeX"):
            if token in text and "tests/" not in str(path):
                raise AssertionError(f"{path} contains {token}")


def test_authenticated_cannot_enable():
    from social.accounts.models import SocialAccount, enable_account
    import pytest
    with pytest.raises(ValueError):
        enable_account(SocialAccount("a", "douyin", "douyin", status="AUTHENTICATED"))


def test_no_china_social_adapter_switch():
    for path in (ROOT / "social").rglob("*.py"):
        if path.name == "resolver.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "class ChinaSocialAdapter" not in text


def test_production_does_not_import_test_fakes():
    for path in _iter_py():
        body = path.read_text(encoding="utf-8")
        if "tests.fakes" in body or "from tests.fakes" in body:
            raise AssertionError(f"{path} imports tests.fakes")


def test_base_verify_capabilities_is_fail_closed():
    from social.providers.base import BaseSocialAdapter
    from social.accounts.models import SocialAccount

    adapter = BaseSocialAdapter()
    adapter.provider = "x"
    adapter.claimed = {"publish": True, "text": True}
    adapter._accounts["a"] = SocialAccount("a", "x", "x", status="AUTHENTICATED")
    caps = adapter.verify_capabilities("a")
    assert caps.verified("publish") is False
    assert caps.records["publish"].method in {"unverified", "probe_required"}
