"""Write analytics insights back into memory as reusable patterns."""

from __future__ import annotations

from typing import Any

from memory.models import MemoryFact
from memory.retrieval import remember


def write_patterns(insight: dict[str, Any]) -> dict[str, Any]:
    facts = []
    mapping = {
        "successful_pattern": "content",
        "failed_pattern": "content",
        "platform_preference": "platform",
        "audience_preference": "feedback",
        "content_pattern": "content",
    }
    for key, namespace in mapping.items():
        if key in insight:
            facts.append(remember(MemoryFact(
                fact_id=f"{namespace}:{key}",
                namespace=namespace,
                subject=key,
                value=insight[key],
                source="analytics-insight",
                confidence=float(insight.get("confidence") or 0.5),
            )))
    if insight.get("kind"):
        facts.append(remember(MemoryFact(
            fact_id=f"insight:{insight.get('kind')}",
            namespace="content",
            subject=str(insight.get("kind")),
            value=insight,
            source="analytics-insight",
            confidence=float(insight.get("confidence") or 0.5),
        )))
    return {"written": len(facts), "facts": facts}
