"""Execute due SCHEDULED/READY jobs. Agents do not sleep(). Native adapter.schedule() is never called."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from integrations.persistence import JobStore
from social.schedule.scheduler import MeitiScheduler


def run_once(*, execute: Callable[[Any], Any] | None = None, store: JobStore | None = None, now: datetime | None = None, worker_id: str = "scheduler") -> list[str]:
    if store is None:
        raise ValueError("scheduler requires an explicit store")
    return MeitiScheduler(store).tick(worker_id=worker_id, now=now, execute=execute)
