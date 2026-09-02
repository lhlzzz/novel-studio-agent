"""Fail-closed checks for DistributionJob admission."""

from integrations.contracts.distribution import DistributionJob


def check_distribution_job(
    job: DistributionJob,
    account,
    *,
    content_valid: bool,
    evidence_valid: bool,
    account_valid: bool,
    media_valid: bool,
    approval_valid: bool,
    provider_verified: bool = False,
    integration_verified: bool = False,
    account_verified: bool = False,
    capability_verified: bool = False,
    idempotency_valid: bool = False,
    media_uploaded: bool = False,
    payload_valid: bool = False,
) -> list[str]:
    failures: list[str] = []
    if not content_valid:
        failures.append("content invalid")
    if not evidence_valid:
        failures.append("evidence invalid")
    if not account_valid:
        failures.append("account invalid")
    enabled = bool(getattr(account, "enabled", False) or getattr(account, "status", "") == "ENABLED")
    if not enabled:
        failures.append("account disabled")
    if not media_valid:
        failures.append("media invalid")
    if not approval_valid:
        failures.append("approval invalid")
    account_id = getattr(account, "id", None) or getattr(account, "account_id", "")
    if job.account_id != account_id:
        failures.append("account mismatch")
    if not provider_verified:
        failures.append("provider unverified")
    verified = bool(
        account_verified
        or integration_verified
        or getattr(account, "verified", False)
        or getattr(account, "status", "") in {"VERIFIED", "ENABLED"}
        or getattr(account, "state", "") in {"VERIFIED", "ENABLED"}
    )
    if not verified:
        failures.append("account not verified")
    if not capability_verified:
        failures.append("capability unverified")
    if not idempotency_valid:
        failures.append("idempotency invalid")
    if not media_uploaded:
        failures.append("media not uploaded")
    if not payload_valid:
        failures.append("payload invalid")
    return failures
