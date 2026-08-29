from integrations.providers.resolver import resolve_adapter, resolve_capability, resolve_provider
from integrations.registry.loader import clear_runtime_state, set_runtime_state
from integrations.contracts.distribution import IntegrationCapabilities


def test_provider_resolver_returns_adapter():
    handle = resolve_provider("postiz")
    assert handle.implementation.__class__.__name__ == "PostizAdapter"
    adapter = resolve_adapter("postiz")
    assert adapter.__class__.__name__ == "PostizAdapter"


def test_unverified_capability_is_not_allowed():
    clear_runtime_state()
    record = resolve_capability("postiz", "publish")
    assert record.verified is False
    set_runtime_state("postiz", state="ENABLED", enabled=True, capabilities=IntegrationCapabilities(publish=True))
    clear_runtime_state()
