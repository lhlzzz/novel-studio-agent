"""Provider-agnostic distribution contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class IntegrationCapabilities:
    publish: bool = False
    schedule: bool = False
    analytics: bool = False
    comments: bool = False
    replies: bool = False
    dm: bool = False
    commerce: bool = False
    media: bool = False
    # Public API capability name; media is retained for V3 compatibility.
    media_upload: bool = False


@dataclass(frozen=True)
class Integration:
    id: str
    provider: str
    account_id: str
    region: str
    capabilities: IntegrationCapabilities
    adapter: str
    distribution_backend: str
    enabled: bool = False


@dataclass(frozen=True)
class ContentVariant:
    integration_id: str
    body: str
    media: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DistributionJob:
    job_id: str
    content_package_id: str
    integration_id: str
    variant: ContentVariant
    action: str = "publish"
    scheduled_at: str | None = None


@dataclass(frozen=True)
class Publication:
    distribution_job_id: str
    postiz_post_id: str
    integration_id: str
    provider: str
    status: str
    published_at: str | None = None
    external_id: str | None = None


class DistributionAdapter(Protocol):
    def list_integrations(self) -> list[Integration]: ...
    def get_integration(self, integration_id: str) -> Integration: ...
    def get_capabilities(self, integration_id: str) -> IntegrationCapabilities: ...
    def validate_payload(self, job: DistributionJob) -> list[str]: ...
    def prepare_publish(self, job: DistributionJob) -> dict[str, Any]: ...
    def publish(self, job: DistributionJob) -> dict[str, Any]: ...
    def schedule(self, job: DistributionJob) -> dict[str, Any]: ...
    def get_status(self, job_id: str) -> dict[str, Any]: ...
    def delete(self, job_id: str) -> dict[str, Any]: ...
    def get_analytics(self, job_id: str) -> dict[str, Any]: ...

    def get_settings(self, integration_id: str) -> dict[str, Any]: ...


class UnsupportedCapabilityError(RuntimeError):
    """Raised when an adapter cannot honestly perform a requested operation."""


def validate_common_payload(job: DistributionJob, integration: Integration) -> list[str]:
    errors: list[str] = []
    if not job.job_id or not job.content_package_id:
        errors.append("job_id and content_package_id are required")
    if job.integration_id != integration.id:
        errors.append("job integration does not match registered integration")
    if not job.variant.body.strip() and not job.variant.media:
        errors.append("content body or media is required")
    if job.action not in {"publish", "schedule"}:
        errors.append(f"unsupported action: {job.action}")
    capability = integration.capabilities.schedule if job.action == "schedule" else integration.capabilities.publish
    if not capability:
        errors.append(f"{job.action} capability is unsupported")
    return errors
