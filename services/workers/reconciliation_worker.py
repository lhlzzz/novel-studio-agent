"""Scan in-flight jobs and reconcile them against the provider. No agent sleep()."""

from __future__ import annotations

from typing import Any

from integrations.persistence import InMemoryStore, JobStore
from services.reconciliation.service import reconcile_distribution_job

IN_FLIGHT = ("SUBMITTED", "SCHEDULED", "PUBLISHING", "UNKNOWN")


def run_once(*, adapter: Any, store: JobStore | None = None) -> list[dict[str, Any]]:
    store = store or InMemoryStore()
    results = []
    for job in store.list_jobs(IN_FLIGHT):
        results.append(reconcile_distribution_job(job.job_id, adapter=adapter, store=store))
    return results


def main() -> None:  # pragma: no cover
    print({"reconciled": len(run_once(adapter=None))})


if __name__ == "__main__":  # pragma: no cover
    main()
