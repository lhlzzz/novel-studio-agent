from content.models import ContentPackage
from integrations.contracts.distribution import ContentVariant, DistributionJob, Integration, IntegrationCapabilities, IllegalJobTransition, make_idempotency_key, transition_job
from integrations.distribution_service import DistributionService
from integrations.persistence import InMemoryStore
from tests.fixtures.fakes import FakeAdapter, job as _job


def test_duplicate_publish_is_idempotent():
    adapter = FakeAdapter()
    store = InMemoryStore()
    service = DistributionService(adapter, store=store)
    job = _job()
    first = service.execute(job, gate_check=lambda item: True)
    second = service.execute(job, gate_check=lambda item: True)
    assert first.provider_post_id == second.provider_post_id == "postiz-post-1"
    assert adapter.published is True
    # FakeAdapter.publish would have been called once because the second call returns stored publication.
    assert store.get_publication(job.job_id).distribution_job_id == job.job_id


def test_illegal_blocked_to_submitting_is_rejected():
    job = DistributionJob("job-1", "pkg-1", "i", ContentVariant("i", "hello"), status="BLOCKED")
    try:
        transition_job(job, "SUBMITTING")
    except IllegalJobTransition:
        return
    raise AssertionError("BLOCKED -> SUBMITTING must be rejected")


def test_idempotency_key_is_stable():
    assert make_idempotency_key("pkg", "int", "publish", None) == make_idempotency_key("pkg", "int", "publish", None)
