"""Fail-closed checks for DistributionJob admission."""

from __future__ import annotations

from typing import Any

from integrations.contracts.distribution import DistributionJob
from social.publish.gate import AdmissionDecision, admit


def check_distribution_job(
    job: DistributionJob,
    account,
    *,
    adapter: Any | None = None,
    store: Any | None = None,
) -> list[str]:
    decision = admit_distribution_job(job, account=account, adapter=adapter, store=store)
    return list(decision.reasons)


def admit_distribution_job(
    job: DistributionJob,
    *,
    account=None,
    adapter: Any | None = None,
    store: Any | None = None,
) -> AdmissionDecision:
    if adapter is None:
        adapter = _AccountAdapter(account)
    return admit(job, adapter=adapter, store=store, account=account)


class _AccountAdapter:
    def __init__(self, account) -> None:
        self.account = account
        self.secrets = None
        self.provider = getattr(account, "provider", "")

    def get_account(self, account_id: str):
        if account_id != getattr(self.account, "account_id", None):
            raise KeyError(account_id)
        return self.account

    def validate_payload(self, job: DistributionJob) -> list[str]:
        from integrations.contracts.distribution import validate_common_payload

        return validate_common_payload(job, self.account.as_integration())

    def health(self):
        from integrations.contracts.distribution import ProviderHealth

        return ProviderHealth(provider=self.provider, reachable=False, authenticated=False)
