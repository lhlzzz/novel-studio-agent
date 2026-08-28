from integrations.registry.loader import load_registry


def test_registry_is_dynamic_and_disabled_until_verified():
    registry = load_registry()
    assert "x" in registry
    assert "instagram" in registry
    assert "xiaohongshu" in registry
    assert all(not integration.enabled for integration in registry.values())
    assert registry["xiaohongshu"].distribution_backend == "custom"


def test_registry_is_not_fixed_to_six_providers():
    assert len(load_registry()) > 6
