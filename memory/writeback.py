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


def write_production(event: dict[str, Any]) -> dict[str, Any]:
    """Persist creative/publication/analytics/research facts for later retrieval."""
    facts = []
    namespace_map = {
        "workflow": "creative",
        "provider": "creative",
        "model": "creative",
        "cost": "creative",
        "creative_run_id": "creative",
        "publication": "publication",
        "platform": "platform",
        "analytics": "analytics",
        "research": "research",
        "artifact": "research",
    }
    kind = str(event.get("kind") or "production")
    for key, namespace in namespace_map.items():
        if key not in event:
            continue
        facts.append(remember(MemoryFact(
            fact_id=f"{namespace}:{kind}:{key}",
            namespace=namespace,
            subject=key,
            value=event[key],
            source=str(event.get("source") or "production"),
            confidence=float(event.get("confidence") or 1.0),
        )))
    if event:
        facts.append(remember(MemoryFact(
            fact_id=f"production:{kind}",
            namespace="content",
            subject=kind,
            value=event,
            source=str(event.get("source") or "production"),
            confidence=float(event.get("confidence") or 1.0),
        )))
    return {"written": len(facts), "facts": facts}
