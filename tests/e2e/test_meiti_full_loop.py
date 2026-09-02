from analytics.insights import build_insight
from analytics.normalizers.metrics import normalize_metrics
from content.models import ContentPackage
from content.variants import build_variant
from governance.distribution_gate import check_distribution_job
from integrations.contracts.distribution import DistributionJob, make_idempotency_key
from integrations.distribution_service import DistributionService
from integrations.persistence import InMemoryStore
from memory.retrieval import retrieve
from services.workers.analytics_worker import run_once
from tests.e2e.fake_x import FakeXAdapter


def test_mock_package_to_memory_loop():
    adapter = FakeXAdapter()
    store = InMemoryStore()
    package = ContentPackage(
        "pkg-e2e",
        "MEITI V4 NATIVE SOCIAL E2E TEST",
        "publish body",
        hook="stop guessing distribution",
        topic="distribution",
        brand_id="brand-a",
        campaign_id="camp-e2e",
    )
    variant = build_variant(package, account_id="x-test", platform="x")
    from dataclasses import replace as _replace
    variant = _replace(variant, metadata={**(variant.metadata or {}), "approval": "approved"})
    job = DistributionJob(
        "job-e2e",
        package.package_id,
        "x-test",
        variant,
        idempotency_key=make_idempotency_key(package.package_id, "x-test", "publish", None),
        request_id="req-e2e",
        campaign_id=package.campaign_id,
    )
    failures = check_distribution_job(job, adapter.account, adapter=adapter)
    assert failures == []
    publication = DistributionService(adapter, store=store).execute(job, gate_check=lambda item: True)
    assert publication.request_id == "req-e2e"
    results = run_once(adapter=adapter, store=store, window="1h")
    metrics = normalize_metrics(publication.distribution_job_id, adapter.get_analytics(publication.provider_post_id), platform="x", post_id=publication.provider_post_id)
    insight = build_insight(metrics)
    memory = retrieve({"query": "hook"})
    assert results
    assert insight.metric == "views"
    assert "historical_successful_patterns" in memory
    assert store.list_attempts("job-e2e")
