"""Typed creative failures. Missing evidence is BLOCKED, never faked."""

from __future__ import annotations


class CreativeError(Exception):
    code = "creative_error"


class UnsupportedCapability(CreativeError):
    code = "unsupported_capability"

    def __init__(self, capability: str, *, provider: str = "") -> None:
        self.capability = capability
        self.provider = provider
        super().__init__(f"unsupported capability: {provider}:{capability}".strip(":"))


class ProviderBlocked(CreativeError):
    code = "provider_blocked"

    def __init__(self, provider: str, reason: str) -> None:
        self.provider = provider
        self.reason = reason
        super().__init__(f"{provider} blocked: {reason}")


class BudgetExceeded(CreativeError):
    code = "budget_exceeded"

    def __init__(self, estimated: float, budget: float) -> None:
        self.estimated = estimated
        self.budget = budget
        super().__init__(f"estimated cost {estimated} exceeds budget {budget}")


class QualityBlocked(CreativeError):
    code = "quality_blocked"

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = tuple(reasons)
        super().__init__("quality gate blocked: " + "; ".join(reasons))


class WorkflowNotFound(CreativeError):
    code = "workflow_not_found"


class IllegalRunTransition(CreativeError):
    code = "illegal_run_transition"

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"illegal run transition: {current} -> {target}")
