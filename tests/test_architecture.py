from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_workspace_and_launchers_are_absent():
    assert not (ROOT / "workspaces").exists()
    assert not (ROOT / "scripts/start_platform_agent.sh").exists()
    assert not (ROOT / "scripts/validate_platform_agents.py").exists()


def test_capability_topology_exists():
    for name in ("agents", "intelligence", "strategy", "content", "media",
                 "analytics", "memory", "commerce", "governance",
                 "workflows", "integrations", "infrastructure"):
        assert (ROOT / name).is_dir(), name


def test_no_fixed_port_topology_in_active_files():
    forbidden = tuple(str(9000 + offset) for offset in range(1, 7))
    active = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "RULES.md",
              ROOT / "STATE.md", ROOT / "TASK.md", ROOT / "TOOLING.md"]
    for path in active:
        text = path.read_text(encoding="utf-8")
        assert not any(port in text for port in forbidden), path
