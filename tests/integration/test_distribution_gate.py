from governance.distribution_gate import check_distribution_job
from integrations.contracts.distribution import ContentVariant, DistributionJob
from social.accounts.models import SocialAccount, SocialProviderCapabilities, enable_account


def _account():
    return enable_account(SocialAccount("i", "x", "x", username="meiti", status="VERIFIED", capabilities=SocialProviderCapabilities(publish=True, text=True)))


def test_distribution_gate_blocks_missing_approval():
    job = DistributionJob("j", "p", "i", ContentVariant("i", "test"))
    failures = check_distribution_job(
        job, _account(), content_valid=True, evidence_valid=True,
        account_valid=True, media_valid=True, approval_valid=False,
        provider_verified=True, integration_verified=True, capability_verified=True,
        idempotency_valid=True, media_uploaded=True, payload_valid=True,
    )
    assert failures == ["approval invalid"]


def test_unverified_capability_blocks():
    job = DistributionJob("j", "p", "i", ContentVariant("i", "test"))
    failures = check_distribution_job(
        job, _account(), content_valid=True, evidence_valid=True,
        account_valid=True, media_valid=True, approval_valid=True,
        provider_verified=True, integration_verified=True, capability_verified=False,
        idempotency_valid=True, media_uploaded=True, payload_valid=True,
    )
    assert "capability unverified" in failures
