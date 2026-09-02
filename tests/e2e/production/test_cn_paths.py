from social.runtime.container import SocialRuntime
from integrations.persistence import InMemoryStore


def test_testing_runtime_allows_memory():
    runtime = SocialRuntime.testing()
    assert isinstance(runtime.store, InMemoryStore)
    assert runtime.production is False


def test_production_runtime_requires_secret_dir(monkeypatch):
    monkeypatch.delenv("MEITI_SECRET_DIR", raising=False)
    from social.auth.secrets import SecretStoreError
    import pytest
    with pytest.raises(SecretStoreError):
        SocialRuntime.production()
