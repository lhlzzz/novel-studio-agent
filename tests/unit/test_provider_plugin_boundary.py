from pathlib import Path

from integrations.providers.resolver import ADAPTER_IMPORTS


def test_new_provider_registers_without_changing_distribution_agent():
    source = Path("agents/distribution_agent.py").read_text(encoding="utf-8")
    assert "PostizAdapter" not in source
    assert "postiz" in ADAPTER_IMPORTS
    assert "resolve_adapter" in source
