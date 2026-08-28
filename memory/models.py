"""Memory service contract over PostgreSQL, pgvector, KG, and Obsidian."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemoryFact:
    fact_id: str
    namespace: str
    subject: str
    value: Any
    source: str
    confidence: float = 1.0
