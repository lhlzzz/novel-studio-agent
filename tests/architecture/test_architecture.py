from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_legacy_workspace_and_launchers_are_absent():
    assert not (ROOT / "workspaces").exists()
    launcher = "start_" + "platform" + "_agent.sh"
    validator = "validate_" + "platform" + "_agents.py"
    assert not (ROOT / "scripts" / launcher).exists()
    assert not (ROOT / "scripts" / validator).exists()


def test_capability_topology_exists():
    for name in ("agents", "intelligence", "strategy", "content", "media",
                 "creative", "analytics", "memory", "commerce", "governance",
                 "workflows", "integrations", "infrastructure"):
        assert (ROOT / name).is_dir(), name


def test_no_fixed_port_topology_in_active_files():
    forbidden = tuple(str(9000 + offset) for offset in range(1, 7))
    active = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "RULES.md",
              ROOT / "STATE.md", ROOT / "TASK.md", ROOT / "TOOLING.md"]
    for path in active:
        text = path.read_text(encoding="utf-8")
        assert not any(port in text for port in forbidden), path


def test_distribution_agent_does_not_import_postiz_adapter_directly():
    source = (ROOT / "agents/distribution_agent.py").read_text(encoding="utf-8")
    assert "PostizAdapter" not in source
    assert "providers.postiz.adapter" not in source


def test_media_agent_does_not_import_lechuang_adapter():
    source = (ROOT / "agents/media/runtime.py").read_text(encoding="utf-8")
    assert "LechuangAdapter" not in source
    assert "providers.lechuang" not in source


def test_creative_does_not_import_postiz():
    forbidden = ("PostizAdapter", "providers.postiz")
    for path in (ROOT / "creative").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert all(token not in text for token in forbidden), path
