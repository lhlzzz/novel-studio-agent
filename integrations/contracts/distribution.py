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
    "CONNECTED",
    "VERIFYING",
    "VERIFIED",
    "ENABLED",
    "DEGRADED",
    "BLOCKED",
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
    "RECONCILING",
    "PROCESSING",
)

JOB_TRANSITIONS = {
    "DRAFT": {"VALIDATING", "SCHEDULED", "READY", "CANCELLED", "BLOCKED"},
    "VALIDATING": {"BLOCKED", "READY", "SCHEDULED", "FAILED"},
    "BLOCKED": {"VALIDATING", "CANCELLED", "DRAFT", "READY", "SCHEDULED"},
    "READY": {"SUBMITTING", "CANCELLED", "BLOCKED", "VALIDATING"},
    "SUBMITTING": {"SUBMITTED", "FAILED", "RETRYING", "UNKNOWN", "BLOCKED", "PUBLISHING"},
    "SUBMITTED": {"SCHEDULED", "PUBLISHING", "PUBLISHED", "FAILED", "UNKNOWN", "RECONCILING"},
    "SCHEDULED": {"READY", "PUBLISHING", "CANCELLED", "FAILED", "UNKNOWN", "BLOCKED"},
    "PUBLISHING": {"PUBLISHED", "FAILED", "UNKNOWN", "PROCESSING"},
    "PROCESSING": {"PUBLISHED", "FAILED", "UNKNOWN", "RECONCILING", "PUBLISHING"},
    "PUBLISHED": set(),
    "FAILED": {"RETRYING", "FAILED_PERMANENT", "CANCELLED", "UNKNOWN"},
    "RETRYING": {"SUBMITTING", "FAILED_PERMANENT", "UNKNOWN"},
    "CANCELLED": set(),
    "UNKNOWN": {"RECONCILING", "SUBMITTED", "SCHEDULED", "PUBLISHING", "PUBLISHED", "FAILED", "CANCELLED", "READY", "RETRYING"},
    "FAILED_PERMANENT": set(),
    "RECONCILING": {"PUBLISHED", "FAILED", "UNKNOWN", "CANCELLED", "SUBMITTED", "SCHEDULED", "PUBLISHING"},
}


@dataclass(frozen=True)
class CapabilityRecord:
    name: str
    supported: bool = False
    verified: bool = False
    authorized: bool = False
    contract_verified: bool = False
    live_verified: bool = False
    verified_at: str | None = None
    method: str = "unverified"
    verification_method: str = ""
    surface: str = "both"
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        if self.live_verified:
            return bool(self.supported)
        return bool(self.supported and self.contract_verified and self.authorized)

    @property
    def verification(self) -> str:
        return self.verification_method or self.method


def make_capability(
    name: str,
    *,
    supported: bool,
    authorized: bool = False,
    contract_verified: bool = False,
    live_verified: bool = False,
    method: str = "unverified",
    evidence: dict[str, Any] | None = None,
    verified_at: str | None = None,
) -> "CapabilityRecord":
    closed = bool(supported and authorized and contract_verified)
    return CapabilityRecord(
        name=name,
        supported=supported,
        authorized=authorized,
        contract_verified=contract_verified,
        live_verified=live_verified,
        verified=closed,
        verified_at=verified_at if closed or live_verified else None,
        method=method,
        verification_method=method,
        evidence=dict(evidence or {}),
    )


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
    platform: str = ""


@dataclass(frozen=True)
class IntegrationAccount:
    platform: str
    integration_id: str
    status: str = "pending"
    provider: str = ""
    account_name: str = ""
    account_id: str = ""
    capabilities: tuple[str, ...] = ()
    verified_at: str | None = None
    enabled: bool = False


@dataclass(frozen=True)
class ContentVariant:
    account_id: str
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

    @property
    def integration_id(self) -> str:
        return self.account_id


@dataclass(frozen=True)
class DistributionJob:
    job_id: str
    content_package_id: str
    account_id: str
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
    lease_until: str | None = None
    worker_id: str | None = None
    claimed_at: str | None = None
    provider: str = ""
    platform: str = ""

    @property
    def integration_id(self) -> str:
        return self.account_id


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
    attempt_id: str = ""
    distribution_job_id: str = ""
    provider: str = ""
    integration_id: str = ""
    provider_object_id: str | None = None

    def __post_init__(self) -> None:
        if not self.attempt_id:
            object.__setattr__(self, "attempt_id", f"{self.job_id}:{self.attempt_no}")
        if not self.distribution_job_id:
            object.__setattr__(self, "distribution_job_id", self.job_id)


@dataclass(frozen=True)
class Publication:
    distribution_job_id: str
    account_id: str
    provider: str
    provider_post_id: str
    platform_object_id: str | None = None
    status: str = "UNKNOWN"
    published_at: str | None = None
    external_url: str | None = None
    content_package_id: str = ""
    request_id: str = ""
    publication_id: str = ""
    platform: str = ""
    created_at: str | None = None
    provider_object_type: str = ""

    def __post_init__(self) -> None:
        if not self.publication_id:
            object.__setattr__(self, "publication_id", f"publication:{self.distribution_job_id}")

    @property
    def id(self) -> str:
        return self.publication_id

    def resolved_provider_post_id(self) -> str:
        return self.provider_post_id

    @property
    def remote_post_id(self) -> str:
        return self.provider_post_id

    @property
    def remote_url(self) -> str | None:
        return self.external_url

    @property
    def object_type(self) -> str:
        return self.provider_object_type

    def resolved_platform_object_id(self) -> str | None:
        return self.platform_object_id

    @property
    def integration_id(self) -> str:
        return self.account_id


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
    account_id: str = ""
    failure_code: str | None = None
    created_at: str | None = None

    @property
    def remote_media_id(self) -> str:
        return self.remote_id

    @property
    def remote_media_path(self) -> str:
        return self.remote_path


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
    account_id: str,
    action: str,
    scheduled_at: str | None = None,
) -> str:
    raw = f"{content_package_id}|{account_id}|{action}|{scheduled_at or ''}"
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
    job_account = getattr(job, "account_id", None) or getattr(job, "integration_id", "")
    if job_account != integration.id:
        errors.append("job account does not match registered account")
    if not job.variant.body.strip() and not job.variant.media:
        errors.append("content body or media is required")
    if job.action not in {"publish", "scheduled_publish", "delete", "cancel"}:
        errors.append(f"unsupported action: {job.action}")
    if job.action in {"publish", "scheduled_publish"}:
        caps = integration.capabilities
        publishable = caps.verified("publish") or caps.verified("handoff") or caps.verified("listing")
        if not publishable:
            errors.append("publish capability is unverified or unsupported")
    state = str(getattr(integration, "state", None) or getattr(integration, "status", "") or "")
    usable = {"ENABLED", "HANDOFF_READY"}
    enabled = bool(getattr(integration, "enabled", False) or state in usable)
    if state not in usable and not enabled:
        errors.append("account is not enabled")
    return errors


@dataclass(frozen=True)
class PublicationOutcome:
    publication: Publication
    job: DistributionJob
    request_id: str = ""
    provider_request_id: str | None = None
    provider_object_id: str = ""
    kind: str = "publication"

    def __getattr__(self, name: str):
        return getattr(self.publication, name)


@dataclass(frozen=True)
class HandoffOutcome:
    handoff: Any
    job: DistributionJob
    request_id: str = ""
    kind: str = "handoff"

    def __getattr__(self, name: str):
        return getattr(self.handoff, name)


@dataclass(frozen=True)
class ListingOutcome:
    listing: Any
    job: DistributionJob
    request_id: str = ""
    provider_request_id: str | None = None
    provider_object_id: str = ""
    kind: str = "listing"


DistributionOutcome = PublicationOutcome | HandoffOutcome | ListingOutcome

