from content.models import ContentPackage
from content.variants import build_variant
from integrations.contracts.distribution import DistributionJob
from integrations.distribution_service import DistributionService
from integrations.persistence import InMemoryStore
from services.workers.analytics_worker import run_once
from tests.e2e.fake_postiz import FakePostizAdapter


def test_meiti_analytics_loop_keeps_null_metrics():
    adapter = FakePostizAdapter()
    store = InMemoryStore()
    package = ContentPackage("pkg-e2e", "MEITI V3 POSTIZ E2E TEST", "body")
    job = DistributionJob("job-e2e", package.package_id, "x-test", build_variant(package, integration_id="x-test", platform="x"))
    DistributionService(adapter, store=store).execute(job, gate_check=lambda item: True)
    results = run_once(adapter=adapter, store=store, window="1h")
    snapshots = results[0]["snapshots"]
    values = {item["metric"]: item["value"] for item in snapshots}
    assert values["views"] == 11
    assert values["likes"] == 2
    assert values["comments"] is None
    assert values["shares"] is None
    assert values["saves"] is None
