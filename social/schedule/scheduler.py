"""Meiti owns scheduling. Workers poll/claim/execute; they never sleep() or call adapter.schedule()."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Callable

from integrations.contracts.distribution import DistributionJob
from integrations.persistence import JobStore


class MeitiScheduler:
    def __init__(self, store: JobStore, *, manager: Any | None = None, adapter: Any | None = None) -> None:
        if store is None:
            raise ValueError("MeitiScheduler requires an explicit store")
        self.store = store
        self.manager = manager
        self.adapter = adapter

    def tick(
        self,
        *,
        worker_id: str,
        now: datetime | None = None,
        execute: Callable[[DistributionJob], Any] | None = None,
        limit: int = 20,
    ) -> list[str]:
        now = now or datetime.now(timezone.utc)
        executed: list[str] = []
        runner = execute or self.execute_claimed
        for _ in range(limit):
            job = self.claim(worker_id=worker_id, now=now)
            if job is None:
                break
            runner(job)
            executed.append(job.job_id)
        return executed

    def claim(self, *, worker_id: str, now: datetime | None = None, lease_seconds: int = 60) -> DistributionJob | None:
        return self.store.claim_due_job(worker_id=worker_id, now=now, lease_seconds=lease_seconds)

    def execute_claimed(self, job: DistributionJob) -> Any:
        from agents.distribution_agent import DistributionAgent

        if self.manager is None:
            raise ValueError("MeitiScheduler requires SocialAccountManager from SocialRuntime")
        agent = DistributionAgent(
            store=self.store,
            manager=self.manager,
            adapter=self.adapter,
            secrets=getattr(self.manager, "secrets", None),
        )
        existing = self.store.get_publication(job.job_id)
        if existing is not None:
            return existing
        handoff = self.store.get_handoff_by_job(job.job_id)
        if handoff is not None:
            return handoff
        listing = self.store.get_listing_by_job(job.job_id)
        if listing is not None:
            return listing
        return agent.execute(job)


def run_once(*, execute: Callable[[Any], Any] | None = None, store: JobStore | None = None, now: datetime | None = None, worker_id: str = "scheduler") -> list[str]:
    if store is None:
        raise ValueError("scheduler run_once requires an explicit store")
    scheduler = MeitiScheduler(store)
    return scheduler.tick(worker_id=worker_id, now=now, execute=execute)
