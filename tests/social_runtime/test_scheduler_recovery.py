from datetime import datetime, timedelta, timezone

from integrations.contracts.distribution import ContentVariant, DistributionJob
from integrations.persistence import InMemoryStore
from social.schedule.scheduler import MeitiScheduler


def test_lease_timeout_allows_other_worker():
    store = InMemoryStore()
    now = datetime(2020, 1, 1, tzinfo=timezone.utc)
    job = DistributionJob("job-1", "pkg", "i", ContentVariant("i", "hello"), status="SCHEDULED", idempotency_key="k", scheduled_at="2000-01-01T00:00:00+00:00")
    store.save_job(job)
    scheduler = MeitiScheduler(store)
    first = scheduler.claim(worker_id="w1", now=now, lease_seconds=60)
    assert first.worker_id == "w1"
    stuck = scheduler.claim(worker_id="w2", now=now, lease_seconds=60)
    assert stuck is None
    recovered = scheduler.claim(worker_id="w2", now=now + timedelta(seconds=61), lease_seconds=60)
    assert recovered is not None
    assert recovered.worker_id == "w2"


def test_future_job_not_claimed():
    store = InMemoryStore()
    now = datetime(2020, 1, 1, tzinfo=timezone.utc)
    job = DistributionJob("job-1", "pkg", "i", ContentVariant("i", "hello"), status="SCHEDULED", idempotency_key="k", scheduled_at="2020-01-02T00:00:00+00:00")
    store.save_job(job)
    assert MeitiScheduler(store).claim(worker_id="w1", now=now) is None


def test_idempotent_scheduler_skips_existing_publication():
    from tests.fakes.social.adapter import FakeAdapter
    from social.runtime.container import SocialRuntime
    runtime = SocialRuntime.testing()
    adapter = FakeAdapter()
    runtime.store.save_account(adapter.account)
    job = DistributionJob("job-1", "pkg", "i", ContentVariant("i", "hello", metadata={"approval": "approved"}), status="READY", idempotency_key="k", provider="x", platform="x")
    runtime.store.save_job(job)
    scheduler = MeitiScheduler(runtime.store, manager=runtime.manager, adapter=adapter)
    first = scheduler.execute_claimed(job)
    second = scheduler.execute_claimed(job)
    assert first.provider_post_id == second.provider_post_id
    assert adapter.published is True
