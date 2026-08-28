from governance.distribution_gate import check_distribution_job
from integrations.contracts.distribution import ContentVariant, DistributionJob, Integration, IntegrationCapabilities


def test_distribution_gate_blocks_missing_approval():
    integration = Integration("i", "x", "a", "global", IntegrationCapabilities(publish=True), "postiz", "postiz", True)
    job = DistributionJob("j", "p", "i", ContentVariant("i", "test"))
    failures = check_distribution_job(job, integration, content_valid=True, evidence_valid=True,
                                      account_valid=True, media_valid=True, approval_valid=False)
    assert failures == ["approval invalid"]
