"""Execute READY jobs whose scheduled_at has arrived. Agents do not sleep()."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from integrations.persistence import InMemoryStore, JobStore


def run_once(*, execute: Callable[[Any], Any], store: JobStore | None = None, now: datetime | None = None) -> list[str]:
    store = store or InMemoryStore()
    now = now or datetime.now(timezone.utc)
    executed = []
    for job in store.list_jobs(("READY", "DRAFT")):
        if not job.scheduled_at:
            continue
        when = datetime.fromisoformat(job.scheduled_at.replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when <= now:
            execute(job)
            executed.append(job.job_id)
    return executed
