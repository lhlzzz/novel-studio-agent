"""Reliable work queue with dead-letter. Reuse this instead of a second worker system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

QUEUE_STATES = ("pending", "processing", "success", "retry", "dead_letter")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class QueueItem:
    item_id: str
    payload: dict[str, Any]
    status: str = "pending"
    attempt_count: int = 0
    last_attempt_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    provider_response: dict[str, Any] | None = None


@dataclass
class WorkQueue:
    items: dict[str, QueueItem] = field(default_factory=dict)
    max_attempts: int = 3

    def enqueue(self, item_id: str, payload: dict[str, Any]) -> QueueItem:
        item = QueueItem(item_id=item_id, payload=payload)
        self.items[item_id] = item
        return item

    def mark(self, item_id: str, status: str, **changes: Any) -> QueueItem:
        if status not in QUEUE_STATES:
            raise ValueError(status)
        item = self.items[item_id]
        for key, value in changes.items():
            setattr(item, key, value)
        item.status = status
        item.last_attempt_at = _utcnow()
        return item

    def fail(self, item_id: str, *, error_code: str, error_message: str, provider_response: dict[str, Any] | None = None) -> QueueItem:
        item = self.items[item_id]
        item.attempt_count += 1
        item.error_code = error_code
        item.error_message = error_message
        item.provider_response = provider_response
        item.last_attempt_at = _utcnow()
        item.status = "dead_letter" if item.attempt_count >= self.max_attempts else "retry"
        return item
