from pathlib import Path


def test_research_skill_boundary_is_documented():
    root = Path(__file__).resolve().parents[1]
    assert "read-only" in (root / "TASK.md").read_text(encoding="utf-8")
    assert "SCRAPECREATORS_API_KEY" in (root / ".env.example").read_text(encoding="utf-8")
