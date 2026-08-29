from content.models import ContentPackage
from content.variants import build_variant
from integrations.contracts.distribution import DistributionJob
from integrations.distribution_service import DistributionService
from tests.e2e.fake_postiz import FakePostizAdapter


def test_meiti_to_postiz_dry_run():
    package = ContentPackage("pkg-e2e", "MEITI V3 POSTIZ E2E TEST", "dry run body")
    variant = build_variant(package, integration_id="x-test", platform="x")
    job = DistributionJob("job-e2e", package.package_id, "x-test", variant)
    result = DistributionService(FakePostizAdapter()).dry_run(job)
    assert result["status"] == "READY"
    assert result["integration_id"] == "x-test"
