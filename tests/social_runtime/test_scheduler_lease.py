from datetime import datetime, timezone
from integrations.contracts.distribution import ContentVariant, DistributionJob
from integrations.persistence import InMemoryStore
from social.schedule.scheduler import MeitiScheduler


def test_two_workers_only_one_claims():
    store = InMemoryStore()
    job = DistributionJob("job-1", "pkg", "i", ContentVariant("i", "hello"), status="SCHEDULED", idempotency_key="k", scheduled_at="2000-01-01T00:00:00+00:00")
    store.save_job(job)
    scheduler = MeitiScheduler(store)
    first = scheduler.claim(worker_id="w1", now=datetime.now(timezone.utc))
    second = scheduler.claim(worker_id="w2", now=datetime.now(timezone.utc))
    assert first is not None
    assert second is None
    assert first.worker_id == "w1"
