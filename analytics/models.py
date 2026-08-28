"""Normalized analytics domain objects."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Account:
    account_id: str
    integration_id: str
    name: str = ""


@dataclass(frozen=True)
class Publication:
    publication_id: str
    distribution_job_id: str
    published_at: str | None = None


@dataclass(frozen=True)
class MetricSnapshot:
    publication_id: str
    metric_name: str
    value: float
    observed_at: str
