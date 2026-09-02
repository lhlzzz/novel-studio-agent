from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = ("agents", "social", "creative", "integrations", "scripts", "services", "governance")


def _iter_py():
    for name in PRODUCTION:
        for path in (ROOT / name).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path


def test_ci_does_not_swallow_doctor_failure():
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        body = path.read_text(encoding="utf-8")
        assert "|| true" not in body, path


def test_no_store_getattr_fallback():
    hits = []
    for path in _iter_py():
        body = path.read_text(encoding="utf-8")
        if "getattr(self.store" in body:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_production_does_not_use_default_secret_store():
    hits = []
    for path in _iter_py():
        rel = str(path.relative_to(ROOT))
        if rel in {"social/auth/secrets.py", "social/auth/__init__.py"}:
            continue
        body = path.read_text(encoding="utf-8")
        if "default_secret_store(" in body:
            hits.append(rel)
    assert hits == []


def test_creative_does_not_import_social_providers():
    creative = ROOT / "creative"
    for path in creative.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        body = path.read_text(encoding="utf-8")
        assert "social.providers" not in body, path


def test_social_providers_do_not_import_creative_runtime():
    for path in (ROOT / "social/providers").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        body = path.read_text(encoding="utf-8")
        assert "creative.runtime" not in body, path
        assert "creative.providers" not in body, path


def test_distribution_does_not_generate_media():
    source = (ROOT / "integrations/distribution_service.py").read_text(encoding="utf-8")
    assert "Lechuang" not in source
    assert "generate_image" not in source
    assert "generate_video" not in source


def test_content_package_is_not_xianyu_listing():
    from commerce.xianyu import XianyuListing
    from content.models import ContentPackage
    package = ContentPackage("pkg", "Title", "Body")
    assert package.__class__ is not XianyuListing
    assert package.commerce_intent == "none"


def test_production_runtime_refuses_inmemory_and_missing_secrets(monkeypatch):
    import pytest
    from integrations.persistence import InMemoryStore
    from social.auth.secrets import SecretStoreError, UnconfiguredSecretStore
    from social.runtime.container import SocialRuntime

    with pytest.raises(ValueError):
        SocialRuntime.create(store=InMemoryStore(), secrets=UnconfiguredSecretStore(), production=True)
    monkeypatch.delenv("MEITI_SECRET_DIR", raising=False)
    with pytest.raises(SecretStoreError):
        SocialRuntime.production()


def test_handoff_never_becomes_publication():
    from social.handoff.models import XHSHandoff
    from integrations.contracts.distribution import Publication
    item = XHSHandoff(handoff_id="h1", account_id="a", content_package_id="p", distribution_job_id="j")
    assert not isinstance(item, Publication)
    assert "provider_post_id" not in item.__dataclass_fields__
