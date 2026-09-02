from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = ("agents", "social", "creative", "integrations", "scripts", "services", "governance")


def _iter_py():
    for name in PRODUCTION:
        for path in (ROOT / name).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path


def test_production_cannot_default_inmemory():
    hits = []
    for path in _iter_py():
        body = path.read_text(encoding="utf-8")
        if "store or InMemoryStore()" in body or "store=None) -> None:\n        from integrations.persistence import InMemoryStore" in body:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_production_cannot_import_tests():
    for path in _iter_py():
        body = path.read_text(encoding="utf-8")
        if "from tests" in body or "import tests" in body:
            raise AssertionError(f"{path} imports tests")


def test_no_execute_ignored_kwargs():
    source = (ROOT / "agents/distribution_agent.py").read_text(encoding="utf-8")
    assert "**_ignored" not in source
    gate = (ROOT / "governance/distribution_gate.py").read_text(encoding="utf-8")
    assert "**_ignored" not in gate


def test_handoff_model_exists():
    from social.handoff.models import XHSHandoff
    item = XHSHandoff(handoff_id="h1", account_id="a", content_package_id="p")
    assert item.status == "READY_FOR_XHS"


def test_job_has_canonical_provider():
    from integrations.contracts.distribution import ContentVariant, DistributionJob
    job = DistributionJob("j", "p", "a", ContentVariant("a", "x"), provider="douyin", platform="douyin")
    assert job.provider == "douyin"
    assert job.platform == "douyin"



def test_no_production_fake_provider():
    for path in _iter_py():
        body = path.read_text(encoding="utf-8")
        if "tests.fakes" in body or "from tests.fakes" in body:
            raise AssertionError(f"{path} references test fakes")


def test_no_production_test_import():
    for path in _iter_py():
        body = path.read_text(encoding="utf-8")
        if "from tests" in body or "import tests." in body:
            raise AssertionError(f"{path} imports tests")


def test_secret_dir_required(monkeypatch):
    monkeypatch.delenv("MEITI_SECRET_DIR", raising=False)
    from social.auth.secrets import SecretStoreError, production_secret_store
    import pytest
    with pytest.raises(SecretStoreError):
        production_secret_store()
