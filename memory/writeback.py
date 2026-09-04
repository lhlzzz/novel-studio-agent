"""Write analytics and production learnings through MemoryService."""

from __future__ import annotations

from typing import Any

from memory.service import get_memory_service


def write_patterns(insight: dict[str, Any]) -> dict[str, Any]:
    return get_memory_service().writeback(insight)


def write_production(event: dict[str, Any]) -> dict[str, Any]:
    payload = dict(event)
    payload.setdefault("source", event.get("source") or "production")
    return get_memory_service().writeback(payload)
