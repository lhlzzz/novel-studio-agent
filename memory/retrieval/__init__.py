"""Retrieve related memory before generating new content.

Production memory is MemoryService. Process-level lists are not a memory system.
"""

from __future__ import annotations

from typing import Any

from content.models import IsolationError
from memory.models import MemoryFact
from memory.service import MemoryService, get_memory_service


def remember(fact: MemoryFact):
    if not fact.account_id:
        raise IsolationError("production memory requires account_id")
    return get_memory_service().remember(
        title=fact.subject,
        content=str(fact.value),
        scope_type=fact.scope_type or "ACCOUNT",
        account_id=fact.account_id,
        platform=fact.platform,
        scope_id=fact.scope_id or fact.account_id,
        source_type=fact.source or "system",
        tags=(fact.namespace, fact.subject),
        document_id=fact.fact_id,
    )


def retrieve(task: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_memory_service().retrieve(task)
