from content.models import ContentPackage
from content.variants import build_variant
from integrations.contracts.distribution import DistributionJob
from integrations.distribution_service import DistributionService
from integrations.persistence import InMemoryStore
from tests.e2e.fake_x import FakeXAdapter


def test_meiti_native_dry_run():
    package = ContentPackage("pkg-e2e", "MEITI V4 NATIVE SOCIAL E2E TEST", "dry run body")
    variant = build_variant(package, account_id="x-test", platform="x")
    job = DistributionJob("job-e2e", package.package_id, "x-test", variant)
    result = DistributionService(FakeXAdapter(), store=InMemoryStore()).dry_run(job)
    assert result["status"] == "READY"
    assert result["account_id"] == "x-test"
