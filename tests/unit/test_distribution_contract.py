from integrations.contracts.distribution import (
    ContentVariant,
    DistributionJob,
    Integration,
    IntegrationCapabilities,
    validate_common_payload,
)
from governance.distribution_gate import check_distribution_job


def _job():
    return DistributionJob("job-1", "pkg-1", "x", ContentVariant("x", "hello"))


def test_content_and_distribution_are_separate_objects():
    job = _job()
    assert job.content_package_id == "pkg-1"
    assert job.variant.integration_id == "x"


def test_disabled_or_unsupported_distribution_fails_closed():
    integration = Integration("x", "x", "", "global", IntegrationCapabilities(), "postiz", "postiz")
    assert validate_common_payload(_job(), integration)
    failures = check_distribution_job(job=_job(), integration=integration,
                                      content_valid=True, evidence_valid=True,
                                      account_valid=True, media_valid=True,
                                      approval_valid=True)
    assert "integration disabled" in failures
