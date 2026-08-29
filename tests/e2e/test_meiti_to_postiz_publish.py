from content.models import ContentPackage
from content.variants import build_variant
from governance.distribution_gate import check_distribution_job
from integrations.contracts.distribution import DistributionJob, make_idempotency_key
from integrations.distribution_service import DistributionService
from integrations.persistence import InMemoryStore
from tests.e2e.fake_postiz import FakePostizAdapter


def test_meiti_to_postiz_publish_persists_publication():
    adapter = FakePostizAdapter()
    store = InMemoryStore()
    package = ContentPackage("pkg-e2e", "MEITI V3 POSTIZ E2E TEST", "publish body", brand_id="brand-a")
    variant = build_variant(package, integration_id="x-test", platform="x")
    job = DistributionJob(
        "job-e2e", package.package_id, "x-test", variant,
        idempotency_key=make_idempotency_key(package.package_id, "x-test", "publish", None),
    )
    failures = check_distribution_job(
        job, adapter.integration, content_valid=True, evidence_valid=True, account_valid=True,
        media_valid=True, approval_valid=True, provider_verified=True, integration_verified=True,
        capability_verified=True, idempotency_valid=True, media_uploaded=True, payload_valid=True,
    )
    assert failures == []
    publication = DistributionService(adapter, store=store).execute(job, gate_check=lambda item: True)
    saved = store.get_publication("job-e2e")
    assert saved.provider_post_id.startswith("postiz-")
    assert saved.platform_object_id.startswith("x-")
    assert saved.distribution_job_id == "job-e2e"
    assert saved.content_package_id == "pkg-e2e"
    again = DistributionService(adapter, store=store).execute(job, gate_check=lambda item: True)
    assert again.provider_post_id == publication.provider_post_id
    assert adapter.published == ["job-e2e"]
