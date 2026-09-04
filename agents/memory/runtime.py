"""Memory agent runtime owns retrieve-before-generate and write-back."""

from __future__ import annotations

from typing import Any

from memory.service import get_memory_service


class MemoryAgent:
    name = "memory-agent"
    owner = "memory"
    capabilities = ("retrieve", "writeback")
    state_store = "postgres:knowledge_documents"
    tests = ("tests/unit/test_memory_retrieval.py", "tests/unit/test_memory_isolation.py")

    def retrieve(self, task: dict[str, Any]) -> dict[str, Any]:
        return get_memory_service().retrieve(task)

    def writeback(self, insight: dict[str, Any]) -> dict[str, Any]:
        return get_memory_service().writeback(insight)

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        if task.get("insight"):
            return self.writeback(dict(task["insight"]))
        return self.retrieve(task)
