from agents.registry import resolve_agent


def test_resolve_agent_returns_implementation_owner_capabilities_status():
    handle = resolve_agent("distribution-agent")
    assert handle.implementation is not None
    assert handle.owner == "distribution"
    assert handle.status == "active"
    assert "execute" in handle.capabilities
    research = resolve_agent("research-agent")
    assert research.owner == "intelligence"
