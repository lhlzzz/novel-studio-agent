"""Typed creative failures. Missing evidence is BLOCKED, never faked."""

from __future__ import annotations


class CreativeError(Exception):
    code = "creative_error"
    retryable = False

    def __init__(self, message: str = "", *, provider: str = "", details: dict | None = None) -> None:
        self.provider = provider
        self.details = dict(details or {})
        super().__init__(message or self.code)

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": user_message(self),
            "provider": self.provider,
            "retryable": self.retryable,
            "details": dict(self.details),
        }


class UnsupportedCapability(CreativeError):
    code = "unsupported_capability"

    def __init__(self, capability: str, *, provider: str = "", details: dict | None = None) -> None:
        self.capability = capability
        super().__init__(
            f"unsupported capability: {provider}:{capability}".strip(":"),
            provider=provider,
            details={"capability": capability, **dict(details or {})},
        )


class ProviderBlocked(CreativeError):
    code = "provider_blocked"

    def __init__(self, provider: str, reason: str, *, details: dict | None = None) -> None:
        self.reason = reason
        super().__init__(
            f"{provider} blocked: {reason}",
            provider=provider,
            details={"reason": reason, **dict(details or {})},
        )


class BudgetExceeded(CreativeError):
    code = "budget_exceeded"

    def __init__(self, estimated: float, budget: float, *, details: dict | None = None) -> None:
        self.estimated = estimated
        self.budget = budget
        super().__init__(
            f"estimated cost {estimated} exceeds budget {budget}",
            details={"estimated": estimated, "budget": budget, **dict(details or {})},
        )


class QualityBlocked(CreativeError):
    code = "quality_blocked"

    def __init__(self, reasons: list[str], *, details: dict | None = None) -> None:
        self.reasons = tuple(reasons)
        super().__init__(
            "quality gate blocked: " + "; ".join(reasons),
            details={"reasons": list(reasons), **dict(details or {})},
        )


class WorkflowNotFound(CreativeError):
    code = "workflow_not_found"

    def __init__(self, workflow_id: str, *, details: dict | None = None) -> None:
        self.workflow_id = workflow_id
        super().__init__(
            f"workflow not found: {workflow_id}",
            details={"workflow_id": workflow_id, **dict(details or {})},
        )


class InvalidStateTransition(CreativeError):
    code = "illegal_run_transition"

    def __init__(self, current: str, target: str, *, details: dict | None = None) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"illegal run transition: {current} -> {target}",
            details={"current": current, "target": target, **dict(details or {})},
        )


IllegalRunTransition = InvalidStateTransition


class SchemaNotReady(CreativeError):
    code = "schema_not_ready"


class PolicyRejected(CreativeError):
    code = "policy_rejected"


class WorkflowInvalid(CreativeError):
    code = "workflow_invalid"

    def __init__(self, reasons: list[str] | str, *, details: dict | None = None) -> None:
        if isinstance(reasons, str):
            reasons = [reasons]
        self.reasons = tuple(reasons)
        super().__init__(
            "workflow invalid: " + "; ".join(self.reasons),
            details={"reasons": list(self.reasons), **dict(details or {})},
        )


class TechnicalMediaError(CreativeError):
    code = "technical_media_failed"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, details=details)


class JudgeBlocked(CreativeError):
    code = "judge_blocked"

    def __init__(self, reason: str, *, provider: str = "judge", details: dict | None = None) -> None:
        self.reason = reason
        super().__init__(
            f"judge blocked: {reason}",
            provider=provider,
            details={"reason": reason, **dict(details or {})},
        )


class AuthError(CreativeError):
    code = "auth_error"


class RateLimited(CreativeError):
    code = "rate_limit"
    retryable = True

    def __init__(self, provider: str, retry_after: float | None = None, *, details: dict | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(
            f"{provider} rate limited",
            provider=provider,
            details={"retry_after": retry_after, **dict(details or {})},
        )


class GenerationTimeout(CreativeError):
    code = "timeout"
    retryable = True

    def __init__(self, message: str = "generation timed out", *, provider: str = "", details: dict | None = None) -> None:
        super().__init__(message, provider=provider, details=details)


class Cancelled(CreativeError):
    code = "cancelled"


FAILURE_CODE_MAP = {
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
    "provider_error": "PROVIDER_UNAVAILABLE",
    "illegal_run_transition": "INVALID_WORKFLOW",
    "schema_not_ready": "INVALID_WORKFLOW",
    "policy_rejected": "POLICY_REJECTED",
}


def failure_code(exc: BaseException) -> str:
    code = getattr(exc, "code", "") or ""
    return FAILURE_CODE_MAP.get(code, "PROVIDER_ERROR")


def user_message(exc: BaseException) -> str:
    if isinstance(exc, ProviderBlocked):
        reason = exc.reason
        lowered = reason.lower()
        if "XIAOLEAI_API_KEY" in reason or "LECHUANG_API_KEY" in reason or "authentication" in lowered or "auth" in lowered:
            return f"{exc.provider} unavailable: authentication required"
        return f"{exc.provider} unavailable: {reason}"
    if isinstance(exc, AuthError):
        return f"{exc.provider or 'provider'} unavailable: authentication required"
    if isinstance(exc, BudgetExceeded):
        return f"budget exceeded: estimated {exc.estimated} > {exc.budget}"
    if isinstance(exc, JudgeBlocked):
        return f"quality judge unavailable: {exc.reason}"
    if isinstance(exc, WorkflowInvalid):
        return "workflow invalid: " + "; ".join(exc.reasons)
    if isinstance(exc, QualityBlocked):
        return "quality gate blocked: " + "; ".join(exc.reasons)
    if isinstance(exc, TechnicalMediaError):
        return f"technical media failed: {exc}"
    if isinstance(exc, RateLimited):
        return f"{exc.provider} rate limited"
    if isinstance(exc, UnsupportedCapability):
        return f"unsupported capability: {exc.provider}:{exc.capability}".strip(":")
    if isinstance(exc, SchemaNotReady):
        return f"creative schema missing: {exc}"
    if isinstance(exc, PolicyRejected):
        return f"policy rejected: {exc}"
    text = str(exc).strip() or exc.__class__.__name__
    if "Traceback" in text:
        return "internal creative error"
    return text
