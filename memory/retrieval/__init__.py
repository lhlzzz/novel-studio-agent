"""Retrieve related memory before generating new content."""

from __future__ import annotations

from typing import Any

from memory.models import MemoryFact

_FACTS: list[MemoryFact] = []


def remember(fact: MemoryFact) -> MemoryFact:
    _FACTS.append(fact)
    return fact


def retrieve(task: dict[str, Any] | None = None) -> dict[str, Any]:
    task = task or {}
    query = str(task.get("query") or task.get("title") or task.get("body") or "").lower()
    related = [
        fact for fact in _FACTS
        if not query or query in fact.subject.lower() or query in str(fact.value).lower()
    ]
    historical_content = [fact for fact in related if fact.namespace == "content"]
    return {
        "historical_content": historical_content,
        "historical_successful_patterns": [fact for fact in historical_content if "success" in fact.subject or "successful" in str(fact.value).lower()],
        "historical_failed_patterns": [fact for fact in historical_content if "fail" in fact.subject or "failed" in str(fact.value).lower()],
        "previous_experiments": [fact for fact in related if fact.namespace == "experiment"],
        "experiments": [fact for fact in related if fact.namespace == "experiment"],
        "audience_insights": [fact for fact in related if fact.namespace in {"feedback", "audience"}],
        "platform_insights": [fact for fact in related if fact.namespace == "platform"],
        "feedback": [fact for fact in related if fact.namespace == "feedback"],
        "platform_performance": [fact for fact in related if fact.namespace == "platform"],
        "brand_knowledge": [fact for fact in related if fact.namespace == "brand"],
        "query": query,
    }
