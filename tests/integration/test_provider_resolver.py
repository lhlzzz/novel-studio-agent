from social.providers.resolver import resolve_adapter, resolve_capability, resolve_provider
from social.providers.registry import clear_runtime_state, set_runtime_state
from social.accounts.models import SocialProviderCapabilities


def test_provider_resolver_returns_adapter():
    handle = resolve_provider("x")
    assert handle.implementation.__class__.__name__ == "XAdapter"
    adapter = resolve_adapter("x")
    assert adapter.__class__.__name__ == "XAdapter"


def test_unverified_capability_is_not_allowed():
    clear_runtime_state()
    record = resolve_capability("x", "publish")
    assert record.verified is False
    set_runtime_state("x", state="ENABLED", enabled=True, capabilities=SocialProviderCapabilities(publish=True, text=True))
    clear_runtime_state()
