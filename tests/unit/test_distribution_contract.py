from integrations.contracts.distribution import (
    ContentVariant,
    DistributionJob,
    validate_common_payload,
)
from governance.distribution_gate import check_distribution_job
from social.accounts.models import SocialAccount, SocialProviderCapabilities


def _job():
    return DistributionJob("job-1", "pkg-1", "x", ContentVariant("x", "hello"))


def test_content_and_distribution_are_separate_objects():
    job = _job()
    assert job.content_package_id == "pkg-1"
    assert job.variant.account_id == "x"
    assert job.variant.integration_id == "x"


def test_disabled_or_unsupported_distribution_fails_closed():
    account = SocialAccount("x", "x", "x", capabilities=SocialProviderCapabilities())
    assert validate_common_payload(_job(), account.as_integration())
    failures = check_distribution_job(job=_job(), account=account)
    assert "account disabled" in failures or "account not enabled" in failures
