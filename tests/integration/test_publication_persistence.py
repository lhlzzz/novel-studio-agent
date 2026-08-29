from integrations.distribution_service import DistributionService
from integrations.persistence import InMemoryStore
from tests.fixtures.fakes import FakeAdapter, job as _job


def test_publication_persisted_and_external_ids_separated():
    store = InMemoryStore()
    publication = DistributionService(FakeAdapter(), store=store).execute(_job(), gate_check=lambda job: True)
    saved = store.get_publication("job-1")
    assert saved is not None
    assert saved.distribution_job_id == "job-1"
    assert saved.provider_post_id == "postiz-post-1"
    assert saved.platform_object_id == "x-status-1"
    assert saved.distribution_job_id != saved.provider_post_id
    assert saved.provider_post_id != saved.platform_object_id
    assert publication.content_package_id == "test-package-001"
