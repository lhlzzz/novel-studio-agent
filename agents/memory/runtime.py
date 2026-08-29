"""Memory agent runtime owns retrieve-before-generate and write-back."""

from __future__ import annotations

from typing import Any

from memory.retrieval import retrieve
from memory.writeback import write_patterns


class MemoryAgent:
    name = "memory-agent"
    owner = "memory"
    capabilities = ("retrieve", "writeback")
    state_store = "postgres:content_embeddings"
    tests = ("tests/test_memory_retrieval.py",)

    def retrieve(self, task: dict[str, Any]) -> dict[str, Any]:
        return retrieve(task)

    def writeback(self, insight: dict[str, Any]) -> dict[str, Any]:
        return write_patterns(insight)

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        if task.get("insight"):
            return self.writeback(dict(task["insight"]))
        return self.retrieve(task)
