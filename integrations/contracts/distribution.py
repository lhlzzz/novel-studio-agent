"""Provider-agnostic distribution contract."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

INTEGRATION_STATES = (
    "DISABLED",
    "REGISTERED",
    "AUTHENTICATING",
    "AUTHENTICATED",
    "VERIFYING",
    "VERIFIED",
    "ENABLED",
    "FAILED",
)

JOB_STATES = (
    "DRAFT",
    "VALIDATING",
    "BLOCKED",
    "READY",
    "SUBMITTING",
    "SUBMITTED",
    "SCHEDULED",
    "PUBLISHING",
    "PUBLISHED",
    "FAILED",
    "RETRYING",
    "CANCELLED",
    "UNKNOWN",
    "FAILED_PERMANENT",
)

JOB_TRANSITIONS = {
    "DRAFT": {"VALIDATING", "CANCELLED"},
    "VALIDATING": {"BLOCKED", "READY", "FAILED"},
    "BLOCKED": {"VALIDATING", "CANCELLED", "DRAFT"},
    "READY": {"SUBMITTING", "CANCELLED", "BLOCKED", "VALIDATING"},
    "SUBMITTING": {"SUBMITTED", "FAILED", "RETRYING"},
    "SUBMITTED": {"SCHEDULED", "PUBLISHING", "PUBLISHED", "FAILED", "UNKNOWN"},
    "SCHEDULED": {"PUBLISHING", "CANCELLED", "FAILED", "UNKNOWN"},
    "PUBLISHING": {"PUBLISHED", "FAILED", "UNKNOWN"},
    "PUBLISHED": set(),
    "FAILED": {"RETRYING", "FAILED_PERMANENT", "CANCELLED"},
    "RETRYING": {"SUBMITTING", "FAILED_PERMANENT"},
    "CANCELLED": set(),
    "UNKNOWN": {"SUBMITTED", "SCHEDULED", "PUBLISHING", "PUBLISHED", "FAILED", "CANCELLED"},
    "FAILED_PERMANENT": set(),
}


@dataclass(frozen=True)
class CapabilityRecord:
    name: str
    supported: bool = False
    verified: bool = False
    verified_at: str | None = None
    method: str = "unverified"
    verification_method: str = ""
    surface: str = "both"

    @property
    def allowed(self) -> bool:
        return self.supported and self.verified

    @property
    def verification(self) -> str:
        return self.verification_method or self.method


@dataclass(frozen=True)
class ProviderCapability:
    name: str
    api: bool = False
    mcp: bool = False

    @property
    def surface(self) -> str:
        if self.api and self.mcp:
            return "both"
        if self.mcp:
            return "mcp_only"
        if self.api:
            return "api_only"
        return "none"


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
    media_upload: bool = False
    records: dict[str, CapabilityRecord] = field(default_factory=dict)

    def verified(self, name: str) -> bool:
        record = self.records.get(name)
        if record is not None:
            return record.allowed
        return bool(getattr(self, name, False))


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
    state: str = "REGISTERED"
    verified_at: str | None = None
    account_name: str = ""


@dataclass(frozen=True)
class IntegrationAccount:
    platform: str
    integration_id: str
    status: str = "pending"
    provider: str = ""
    account_name: str = ""


@dataclass(frozen=True)
class ContentVariant:
    integration_id: str
    body: str
    media: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    title: str = ""
    hashtags: tuple[str, ...] = ()
    cta: str = ""
    constraints: dict[str, Any] = field(default_factory=dict)
    caption: str = ""
    hook: str = ""
    format: str = ""


@dataclass(frozen=True)
class DistributionJob:
    job_id: str
    content_package_id: str
    integration_id: str
    variant: ContentVariant
    action: str = "publish"
    scheduled_at: str | None = None
    status: str = "DRAFT"
    idempotency_key: str | None = None
    attempt_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    last_attempt_at: str | None = None
    provider_response: dict[str, Any] | None = None
    brand_id: str | None = None
    creator_id: str | None = None
    campaign_id: str | None = None
    request_id: str = ""


@dataclass(frozen=True)
class DistributionAttempt:
    job_id: str
    attempt_no: int
    started_at: str
    finished_at: str | None = None
    status: str = "processing"
    error_code: str | None = None
    error_message: str | None = None
    provider_request_id: str | None = None
    response_summary: dict[str, Any] | None = None
    request_id: str = ""


@dataclass(frozen=True)
class Publication:
    distribution_job_id: str
    integration_id: str
    provider: str
    provider_post_id: str
    platform_object_id: str | None = None
    status: str = "UNKNOWN"
    published_at: str | None = None
    external_url: str | None = None
    content_package_id: str = ""
    request_id: str = ""

    def resolved_provider_post_id(self) -> str:
        return self.provider_post_id

    def resolved_platform_object_id(self) -> str | None:
        return self.platform_object_id


@dataclass(frozen=True)
class MediaUploadResult:
    source_hash: str
    source_path: str
    mime_type: str
    size: int
    provider: str
    remote_id: str
    remote_path: str
    uploaded_at: str
    status: str = "uploaded"


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    reachable: bool = False
    authenticated: bool = False
    account_count: int = 0
    last_successful_publish: str | None = None
    last_error: str | None = None
    rate_limit_state: str = "unknown"


class DistributionAdapter(Protocol):
    def authenticate(self) -> bool: ...
    def health(self) -> ProviderHealth: ...
    def list_integrations(self) -> list[Integration]: ...
    def get_capabilities(self, integration_id: str) -> IntegrationCapabilities: ...
    def upload_media(self, source_path: str) -> MediaUploadResult: ...
    def publish(self, job: DistributionJob) -> dict[str, Any]: ...
    def schedule(self, job: DistributionJob) -> dict[str, Any]: ...
    def get_status(self, provider_post_id: str) -> dict[str, Any]: ...
    def cancel(self, provider_post_id: str) -> dict[str, Any]: ...
    def get_analytics(self, provider_post_id: str) -> dict[str, Any]: ...


class UnsupportedCapabilityError(RuntimeError):
    """Raised when an adapter cannot honestly perform a requested operation."""


class ProviderError(RuntimeError):
    """Provider-neutral failure. Retry only when retryable is True."""

    retryable = False


class IllegalJobTransition(RuntimeError):
    """Raised when a DistributionJob cannot move to the requested status."""


def make_idempotency_key(
    content_package_id: str,
    integration_id: str,
    action: str,
    scheduled_at: str | None = None,
) -> str:
    raw = f"{content_package_id}|{integration_id}|{action}|{scheduled_at or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def transition_job(job: DistributionJob, new_status: str, **changes: Any) -> DistributionJob:
    allowed = JOB_TRANSITIONS.get(job.status, set())
    if new_status != job.status and new_status not in allowed:
        raise IllegalJobTransition(f"{job.status} -> {new_status} is not allowed")
    return replace(job, status=new_status, **changes)


def validate_common_payload(job: DistributionJob, integration: Integration) -> list[str]:
    errors: list[str] = []
    if not job.job_id or not job.content_package_id:
        errors.append("job_id and content_package_id are required")
    if job.integration_id != integration.id:
        errors.append("job integration does not match registered integration")
    if not job.variant.body.strip() and not job.variant.media:
        errors.append("content body or media is required")
    if job.action not in {"publish", "schedule", "delete", "cancel"}:
        errors.append(f"unsupported action: {job.action}")
    capability_name = "schedule" if job.action == "schedule" else "publish"
    if job.action in {"publish", "schedule"} and not integration.capabilities.verified(capability_name):
        errors.append(f"{job.action} capability is unverified or unsupported")
    if not integration.enabled or integration.state not in {"ENABLED", "VERIFIED"}:
        if not integration.enabled:
            errors.append("integration is not enabled")
    return errors
