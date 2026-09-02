"""Reconcile Meiti jobs and publications against native provider status."""

from social.reconciliation.service import (
    SocialReconciliationService,
    reconcile_distribution_job,
    reconcile_publication,
)

def reconcile_provider_status(raw: dict) -> str:
    from social.reconciliation.service import _mapped
    return _mapped(str(raw.get("status") or raw.get("state") or "unknown"))

__all__ = [
    "SocialReconciliationService",
    "reconcile_distribution_job",
    "reconcile_publication",
    "reconcile_provider_status",
]
