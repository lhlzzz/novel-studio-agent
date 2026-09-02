from content.models import ContentPackage
from content.variants import build_variant
from integrations.contracts.distribution import DistributionJob
from integrations.distribution_service import DistributionService
from integrations.persistence import InMemoryStore
from social.reconciliation.service import reconcile_distribution_job
from services.workers.reconciliation_worker import run_once
from tests.e2e.fake_x import FakeXAdapter


def test_meiti_reconciliation_updates_publication_status():
    adapter = FakeXAdapter()
    store = InMemoryStore()
    package = ContentPackage("pkg-e2e", "MEITI V4 NATIVE SOCIAL E2E TEST", "body")
    job = DistributionJob("job-e2e", package.package_id, "x-test", build_variant(package, account_id="x-test", platform="x"), provider="x", platform="x")
    DistributionService(adapter, store=store).execute(job, gate_check=lambda item: True)
    result = reconcile_distribution_job("job-e2e", adapter=adapter, store=store)
    assert result["status"] == "PUBLISHED"
    assert result["provider_post_id"] != result["distribution_job_id"]
    scanned = run_once(adapter=adapter, store=store)
    assert isinstance(scanned, list)
