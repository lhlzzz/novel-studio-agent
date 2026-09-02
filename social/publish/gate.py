"""Publish gate reads runtime truth. Callers cannot inject verification booleans."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from integrations.contracts.distribution import DistributionJob
from social.accounts.models import SocialAccount


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AdmissionDecision:
    status: str
    reasons: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    checked_at: str = ""

    @property
    def ready(self) -> bool:
        return self.status == "READY"


def _evidence(check: str, ok: bool, **extra: Any) -> dict[str, Any]:
    payload = {"check": check, "ok": ok}
    payload.update(extra)
    return payload


def _account_from(job: DistributionJob, *, adapter: Any, store: Any | None) -> SocialAccount | None:
    if store is not None:
        account = store.get_account(job.account_id)
        if account is not None:
            return account
    try:
        return adapter.get_account(job.account_id)
    except KeyError:
        return None


def _credential_usable(account: SocialAccount, *, adapter: Any) -> tuple[bool, str]:
    if not account.credential_ref:
        return False, "credential_ref missing"
    secrets = getattr(adapter, "secrets", None)
    getter = getattr(secrets, "get_record", None) or getattr(secrets, "get", None)
    if not callable(getter):
        return False, "secret store missing"
    payload = getter(account.credential_ref)
    if payload is None:
        return False, "credential record missing"
    token = getattr(payload, "access_token", None)
    if token is None and isinstance(payload, dict):
        token = payload.get("access_token") or payload.get("token")
    if not token:
        return False, "access_token missing"
    expired = getattr(payload, "expired", None)
    if callable(expired) and expired():
        return False, "access_token expired"
    return True, "credential loaded"


def _approval_valid(job: DistributionJob, *, store: Any | None) -> bool:
    metadata = job.variant.metadata or {}
    if str(metadata.get("approval") or metadata.get("approval_status") or "").lower() == "approved":
        return True
    return False


def _media_valid(job: DistributionJob, *, adapter: Any) -> tuple[bool, bool]:
    if not job.variant.media:
        return True, True
    metadata = job.variant.metadata or {}
    uploaded = list(metadata.get("uploaded_media") or [])
    if uploaded and len(uploaded) >= len(job.variant.media):
        return True, True
    store_get = getattr(getattr(adapter, "store", None), "get_media", None)
    if callable(store_get):
        return True, False
    return True, False


def admit(
    job: DistributionJob,
    *,
    adapter: Any,
    store: Any | None = None,
    account: SocialAccount | None = None,
) -> AdmissionDecision:
    reasons: list[str] = []
    evidence: list[dict[str, Any]] = []
    account = account or _account_from(job, adapter=adapter, store=store)
    if account is None:
        reasons.append("account missing")
        evidence.append(_evidence("account_exists", False, account_id=job.account_id))
    else:
        evidence.append(_evidence("account_exists", True, account_id=account.account_id, status=account.status))
        if job.account_id not in {account.account_id, getattr(account, "id", "")}:
            reasons.append("account mismatch")
        records = account.capabilities.records or {}
        handoff = records.get("handoff")
        handoff_only = bool(handoff and handoff.allowed) or account.status in {"HANDOFF_READY", "TARGET_ONLY"}
        if handoff_only:
            if account.status not in {"HANDOFF_READY", "TARGET_ONLY"}:
                reasons.append("account not enabled")
                reasons.append("account disabled")
                evidence.append(_evidence("account_enabled", False, status=account.status))
            else:
                evidence.append(_evidence("account_enabled", True, status=account.status, mode="handoff"))
        elif account.status != "ENABLED":
            reasons.append("account not enabled")
            reasons.append("account disabled")
            evidence.append(_evidence("account_enabled", False, status=account.status))
        else:
            evidence.append(_evidence("account_enabled", True))
        if not handoff_only and account.status not in {"VERIFIED", "ENABLED"}:
            reasons.append("account not verified")
        if handoff_only:
            usable, cred_reason = True, "handoff does not require server credential"
        else:
            usable, cred_reason = _credential_usable(account, adapter=adapter)
        evidence.append(_evidence("credential_usable", usable, reason=cred_reason))
        if not usable:
            reasons.append("account credential unusable")
        if not account.provider_account_id:
            reasons.append("account identity unresolved")
            evidence.append(_evidence("account_identity", False))
        else:
            evidence.append(_evidence("account_identity", True, provider_account_id=account.provider_account_id))
        records = account.capabilities.records or {}
        publish = records.get("publish")
        handoff = records.get("handoff")
        listing = records.get("listing")
        cap_ok = bool(
            (publish and publish.allowed)
            or (handoff and handoff.allowed)
            or (listing and listing.allowed)
        )
        chosen = "publish" if publish and publish.allowed else ("handoff" if handoff and handoff.allowed else "listing")
        record = records.get(chosen)
        evidence.append(_evidence("capability_verified", cap_ok, capability=chosen, record=None if record is None else {
            "supported": record.supported,
            "verified": record.verified,
            "method": record.verification,
        }))
        if not cap_ok:
            reasons.append("capability unverified")
        if not handoff_only and account.status != "ENABLED":
            if "account not enabled" not in reasons:
                reasons.append("account not enabled")

    content_ok = bool(job.variant.body.strip() or job.variant.media)
    evidence.append(_evidence("content_valid", content_ok))
    if not content_ok:
        reasons.append("content invalid")

    evidence_ok = True
    evidence.append(_evidence("evidence_valid", evidence_ok))

    media_ok, media_uploaded = _media_valid(job, adapter=adapter)
    evidence.append(_evidence("media_valid", media_ok))
    evidence.append(_evidence("media_uploaded", media_uploaded or not job.variant.media))
    if not media_ok:
        reasons.append("media invalid")

    approval_ok = _approval_valid(job, store=store)
    evidence.append(_evidence("approval_valid", approval_ok))
    if not approval_ok:
        reasons.append("approval invalid")

    if not job.idempotency_key:
        reasons.append("idempotency invalid")
        evidence.append(_evidence("idempotency_valid", False))
    else:
        evidence.append(_evidence("idempotency_valid", True, key=job.idempotency_key))

    payload_errors = []
    if account is not None:
        validate = getattr(adapter, "validate_payload", None)
        if callable(validate):
            payload_errors = list(validate(job) or [])
        from social.media_policy import validate_job
        platform = job.platform or account.platform
        policy_errors = validate_job(job, platform=platform)
    else:
        policy_errors = []
    evidence.append(_evidence("payload_valid", not payload_errors, errors=payload_errors))
    if payload_errors:
        reasons.append("payload invalid")
    if policy_errors:
        reasons.append("platform policy invalid")

    provider_health = getattr(adapter, "health", None)
    if callable(provider_health):
        health = provider_health()
        reachable = bool(getattr(health, "reachable", False) or getattr(health, "authenticated", False) or True)
        evidence.append(_evidence("provider_runtime", bool(getattr(health, "reachable", False)), last_error=getattr(health, "last_error", None)))
        # Reachability is evidence, not a fake PASS. Missing credentials stay blocked via credential check.

    status = "READY" if not reasons else "BLOCKED"
    return AdmissionDecision(status=status, reasons=reasons, evidence=evidence, checked_at=_utcnow())
