"""Experiment objects with an observation window. One result never auto-edits Strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Hypothesis:
    statement: str
    metric: str


@dataclass(frozen=True)
class ExperimentVariant:
    variant_id: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentMetric:
    name: str
    baseline: float | None = None
    sample_size: int = 0


@dataclass(frozen=True)
class ExperimentOutcome:
    result: str | None = None
    confidence: float = 0.0
    winner: str | None = None


@dataclass(frozen=True)
class ExperimentDecision:
    decision: str = "hold"
    reason: str = "observation window has not closed"


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    hypothesis: Hypothesis
    control: ExperimentVariant
    variants: tuple[ExperimentVariant, ...]
    metric: str
    sample_size: int = 30
    primary_metric: str = "views"
    observation_window: str = "7d"
    baseline: float | None = None
    outcome: ExperimentOutcome = field(default_factory=ExperimentOutcome)
    decision: ExperimentDecision = field(default_factory=ExperimentDecision)


# Back-compat names used by existing tests.
Variant = ExperimentVariant

SUPPORTED_KINDS = (
    "hook",
    "title",
    "thumbnail",
    "posting_time",
    "cta",
    "content_format",
    "format",
    "workflow",
    "model",
    "character",
    "camera",
    "motion",
    "duration",
    "aspect_ratio",
)


def create_experiment(kind: str, *, control: dict[str, Any], challenger: dict[str, Any], metric: str = "views") -> Experiment:
    resolved = "content_format" if kind == "format" else kind
    if resolved not in SUPPORTED_KINDS:
        raise ValueError(f"unsupported experiment kind: {kind}")
    return Experiment(
        experiment_id=f"exp-{resolved}",
        hypothesis=Hypothesis(f"{resolved} B outperforms control on {metric}", metric),
        control=ExperimentVariant("control", resolved, control),
        variants=(ExperimentVariant("challenger", resolved, challenger),),
        metric=metric,
        primary_metric=metric,
        observation_window="7d",
        sample_size=30,
        outcome=ExperimentOutcome(result=None, confidence=0.0),
        decision=ExperimentDecision(decision="hold", reason="need observation window before changing strategy"),
    )
