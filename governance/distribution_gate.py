"""Fail-closed checks for DistributionJob admission."""

from integrations.contracts.distribution import DistributionJob, Integration


def check_distribution_job(
    job: DistributionJob,
    integration: Integration,
    *,
    content_valid: bool,
    evidence_valid: bool,
    account_valid: bool,
    media_valid: bool,
    approval_valid: bool,
) -> list[str]:
    failures: list[str] = []
    if not content_valid:
        failures.append("content invalid")
    if not evidence_valid:
        failures.append("evidence invalid")
    if not account_valid:
        failures.append("account invalid")
    if not integration.enabled:
        failures.append("integration disabled")
    if not media_valid:
        failures.append("media invalid")
    if not approval_valid:
        failures.append("approval invalid")
    if job.integration_id != integration.id:
        failures.append("integration mismatch")
    return failures
