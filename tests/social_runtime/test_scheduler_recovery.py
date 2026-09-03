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


def test_unknown_external_action_reconciles():
    from integrations.contracts.distribution import ContentVariant, DistributionJob, Publication
    from integrations.distribution_service import DistributionService, PublicationPersistenceError
    from integrations.persistence import InMemoryStore
    from tests.fakes.social.adapter import FakeAdapter
    import pytest

    store = InMemoryStore()
    adapter = FakeAdapter()
    store.save_account(adapter.account)
    job = DistributionJob(
        "job-unknown",
        "pkg",
        "i",
        ContentVariant("i", "hello", metadata={"approval": "approved"}),
        status="DRAFT",
        idempotency_key="k-unknown",
        provider="x",
        platform="x",
    )
    store.save_job(job)
    original = store.save_publication

    def boom(publication):
        raise RuntimeError("db down")

    store.save_publication = boom
    service = DistributionService(adapter, store=store)
    with pytest.raises(PublicationPersistenceError):
        service.execute(job, gate_check=lambda item: True)
    failed = store.get_job("job-unknown")
    assert failed.status == "UNKNOWN"
    store.save_publication = original
    from social.reconciliation.service import SocialReconciliationService
    recovered = SocialReconciliationService(adapter, store=store).reconcile("job-unknown")
    assert recovered["status"] in {"PUBLISHED", "UNKNOWN"}
    assert store.get_publication("job-unknown") is not None
    assert adapter.published is True


def test_worker_dies_before_publish_can_reclaim():
    store = InMemoryStore()
    now = datetime(2020, 1, 1, tzinfo=timezone.utc)
    job = DistributionJob("job-1", "pkg", "i", ContentVariant("i", "hello"), status="SCHEDULED", idempotency_key="k", scheduled_at="2000-01-01T00:00:00+00:00")
    store.save_job(job)
    first = MeitiScheduler(store).claim(worker_id="w1", now=now, lease_seconds=30)
    assert first is not None
    # worker died before publish: lease expires, another worker reclaims, no duplicate claim while leased
    assert MeitiScheduler(store).claim(worker_id="w2", now=now, lease_seconds=30) is None
    recovered = MeitiScheduler(store).claim(worker_id="w2", now=now + timedelta(seconds=31), lease_seconds=30)
    assert recovered.worker_id == "w2"


def test_worker_dies_after_provider_accepted_does_not_republish():
    from tests.fakes.social.adapter import FakeAdapter
    from social.runtime.container import SocialRuntime
    runtime = SocialRuntime.testing()
    adapter = FakeAdapter()
    runtime.store.save_account(adapter.account)
    job = DistributionJob("job-1", "pkg", "i", ContentVariant("i", "hello", metadata={"approval": "approved"}), status="READY", idempotency_key="k", provider="x", platform="x")
    runtime.store.save_job(job)
    scheduler = MeitiScheduler(runtime.store, manager=runtime.manager, adapter=adapter)
    first = scheduler.execute_claimed(job)
    # crash after provider accepted + persistence: second worker must reuse publication
    second = scheduler.execute_claimed(job)
    assert first.provider_post_id == second.provider_post_id
    assert adapter.published is True
