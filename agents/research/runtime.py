"""Research agent runtime. Live calls require ScrapeCreators credentials."""

from __future__ import annotations

from typing import Any

from intelligence.router import route_research


class ResearchAgent:
    name = "research-agent"
    owner = "intelligence"
    capabilities = ("trend", "outlier", "competitor", "comment", "demand", "creator", "audience", "ads")
    state_store = "postgres:agent_records"
    tests = ("tests/test_research_skills.py", "tests/test_research_runtime.py")

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        return route_research(task)
