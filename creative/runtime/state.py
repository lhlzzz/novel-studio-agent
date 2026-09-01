"""Creative run state machine. Illegal transitions fail closed."""

from __future__ import annotations

from creative.errors import IllegalRunTransition
from creative.schemas import RUN_TRANSITIONS, utcnow

InvalidStateTransition = IllegalRunTransition

BLOCK_REASONS = (
    "CAPABILITY_UNAVAILABLE",
    "PROVIDER_UNAVAILABLE",
    "PROVIDER_AUTH_MISSING",
    "PROVIDER_CONTRACT_UNVERIFIED",
    "BUDGET_EXCEEDED",
    "POLICY_REJECTED",
    "INVALID_WORKFLOW",
    "INVALID_INPUT",
    "RESEARCH_UNAVAILABLE",
    "DISTRIBUTION_UNAVAILABLE",
    "JUDGE_UNAVAILABLE",
    "QUALITY_FAILED",
    "TECHNICAL_MEDIA_FAILED",
    "TIMEOUT",
    "CANCELLED",
)


class BlockReason:
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_AUTH_MISSING = "PROVIDER_AUTH_MISSING"
    PROVIDER_CONTRACT_UNVERIFIED = "PROVIDER_CONTRACT_UNVERIFIED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    POLICY_REJECTED = "POLICY_REJECTED"
    INVALID_WORKFLOW = "INVALID_WORKFLOW"
    INVALID_INPUT = "INVALID_INPUT"
    RESEARCH_UNAVAILABLE = "RESEARCH_UNAVAILABLE"
    DISTRIBUTION_UNAVAILABLE = "DISTRIBUTION_UNAVAILABLE"
    JUDGE_UNAVAILABLE = "JUDGE_UNAVAILABLE"
    QUALITY_FAILED = "QUALITY_FAILED"
    TECHNICAL_MEDIA_FAILED = "TECHNICAL_MEDIA_FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"

RETRYABLE_REASONS = frozenset({"TIMEOUT", "PROVIDER_UNAVAILABLE"})

ERROR_TO_BLOCK = {
    "unsupported_capability": "CAPABILITY_UNAVAILABLE",
    "provider_blocked": "PROVIDER_UNAVAILABLE",
    "budget_exceeded": "BUDGET_EXCEEDED",
    "quality_blocked": "QUALITY_FAILED",
    "workflow_not_found": "INVALID_WORKFLOW",
    "workflow_invalid": "INVALID_WORKFLOW",
    "technical_media_failed": "TECHNICAL_MEDIA_FAILED",
    "judge_blocked": "JUDGE_UNAVAILABLE",
    "auth_error": "PROVIDER_AUTH_MISSING",
    "rate_limit": "PROVIDER_UNAVAILABLE",
    "timeout": "TIMEOUT",
    "cancelled": "CANCELLED",
    "schema_not_ready": "INVALID_WORKFLOW",
    "policy_rejected": "POLICY_REJECTED",
}


def transition(run, status: str):
    allowed = RUN_TRANSITIONS.get(run.status, set())
    if status != run.status and status not in allowed:
        raise InvalidStateTransition(run.status, status)
    run.status = status
    if status == "RUNNING" and not run.started_at:
        run.started_at = utcnow()
    if status in {"SUCCEEDED", "FAILED", "CANCELLED", "BLOCKED"}:
        run.completed_at = utcnow()
    return run


def apply_block(run, reason: str, message: str, *, retryable: bool | None = None):
    code = reason if reason in BLOCK_REASONS else ERROR_TO_BLOCK.get(reason, reason or "PROVIDER_UNAVAILABLE")
    run.blocked_reason = code
    run.blocked_message = message
    run.blocked_at = utcnow()
    run.retryable = bool(RETRYABLE_REASONS.__contains__(code) if retryable is None else retryable)
    run.error = message
    run.error_code = code
    return transition(run, "BLOCKED")


def block_reason_for(exc: BaseException) -> str:
    code = getattr(exc, "code", "") or ""
    if code == "provider_blocked":
        text = str(getattr(exc, "reason", "") or exc)
        lowered = text.lower()
        if "LECHUANG_API_KEY" in text or "auth" in lowered:
            return "PROVIDER_AUTH_MISSING"
        if "contract" in lowered or "unverified" in lowered:
            return "PROVIDER_CONTRACT_UNVERIFIED"
        if "unverified" in lowered or "capability" in lowered:
            return "CAPABILITY_UNAVAILABLE"
        return "PROVIDER_UNAVAILABLE"
    return ERROR_TO_BLOCK.get(code, "PROVIDER_UNAVAILABLE")
