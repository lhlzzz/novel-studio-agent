"""SocialAccount is Meiti's source of truth for native platform accounts."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from integrations.contracts.distribution import CapabilityRecord, Integration, IntegrationCapabilities

ACCOUNT_STATES = (
    "PENDING",
    "AUTHENTICATING",
    "AUTHENTICATED",
    "VERIFYING",
    "VERIFIED",
    "ENABLED",
    "DEGRADED",
    "EXPIRED",
    "REVOKED",
    "BLOCKED",
)

ACCOUNT_TRANSITIONS = {
    "PENDING": {"AUTHENTICATING", "BLOCKED"},
    "AUTHENTICATING": {"AUTHENTICATED", "BLOCKED", "PENDING"},
    "AUTHENTICATED": {"VERIFYING", "EXPIRED", "REVOKED", "BLOCKED", "DEGRADED"},
    "VERIFYING": {"VERIFIED", "AUTHENTICATED", "EXPIRED", "REVOKED", "BLOCKED", "DEGRADED"},
    "VERIFIED": {"ENABLED", "EXPIRED", "REVOKED", "BLOCKED", "DEGRADED", "AUTHENTICATED", "VERIFYING"},
    "ENABLED": {"DEGRADED", "EXPIRED", "REVOKED", "BLOCKED", "VERIFIED"},
    "DEGRADED": {"ENABLED", "EXPIRED", "REVOKED", "BLOCKED", "VERIFIED"},
    "EXPIRED": {"AUTHENTICATING", "AUTHENTICATED", "REVOKED", "BLOCKED"},
    "REVOKED": {"PENDING", "AUTHENTICATING"},
    "BLOCKED": {"PENDING", "AUTHENTICATING", "EXPIRED", "REVOKED"},
}

ENABLED_FROM = frozenset({"VERIFIED"})


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class IllegalAccountTransition(ValueError):
    """Raised when a SocialAccount cannot move to the requested status."""


def transition_account(account: "SocialAccount", new_status: str, **changes: Any) -> "SocialAccount":
    if new_status not in ACCOUNT_STATES:
        raise ValueError(f"invalid account status: {new_status}")
    allowed = ACCOUNT_TRANSITIONS.get(account.status, set())
    if new_status != account.status and new_status not in allowed:
        raise IllegalAccountTransition(f"{account.status} -> {new_status} is not allowed")
    return replace(account, status=new_status, updated_at=_utcnow(), **changes)


@dataclass(frozen=True)
class SocialProviderCapabilities:
    text: bool = False
    image: bool = False
    video: bool = False
    carousel: bool = False
    story: bool = False
    reel: bool = False
    thread: bool = False
    publish: bool = False
    schedule: bool = False
    analytics: bool = False
    media_upload: bool = False
    listing: bool = False
    listing_edit: bool = False
    listing_delete: bool = False
    handoff: bool = False
    records: dict[str, CapabilityRecord] = field(default_factory=dict)

    def verified(self, name: str) -> bool:
        record = self.records.get(name)
        if record is not None:
            return record.allowed
        return False

    def claimed(self) -> dict[str, bool]:
        return {
            "text": self.text,
            "image": self.image,
            "video": self.video,
            "carousel": self.carousel,
            "story": self.story,
            "reel": self.reel,
            "thread": self.thread,
            "publish": self.publish,
            "schedule": self.schedule,
            "analytics": self.analytics,
            "media_upload": self.media_upload,
            "listing": self.listing,
            "listing_edit": self.listing_edit,
            "listing_delete": self.listing_delete,
            "handoff": self.handoff,
        }

    def serialized(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        names = set(self.claimed()) | set(self.records)
        for name in sorted(names):
            record = self.records.get(name)
            supported = record.supported if record is not None else bool(getattr(self, name, False))
            payload[name] = {
                "supported": supported,
                "verified": bool(record.verified) if record is not None else False,
                "verified_at": record.verified_at if record is not None else None,
                "method": record.method if record is not None else "unverified",
                "verification_method": (record.verification_method or record.method) if record is not None else "unverified",
            }
        return payload

    def to_integration(self) -> IntegrationCapabilities:
        records = dict(self.records)
        for name, supported in self.claimed().items():
            records.setdefault(
                name,
                CapabilityRecord(name=name, supported=supported, verified=False, method="registry_claim"),
            )
        return IntegrationCapabilities(
            publish=self.verified("publish"),
            schedule=False,
            analytics=self.verified("analytics"),
            media=self.verified("image") or self.verified("video") or self.verified("reel"),
            media_upload=self.verified("media_upload"),
            records=records,
        )

    @classmethod
    def from_records(cls, records: dict[str, CapabilityRecord]) -> "SocialProviderCapabilities":
        claimed = {name: record.supported for name, record in records.items()}
        return cls(
            text=bool(claimed.get("text")),
            image=bool(claimed.get("image")),
            video=bool(claimed.get("video")),
            carousel=bool(claimed.get("carousel")),
            story=bool(claimed.get("story")),
            reel=bool(claimed.get("reel")),
            thread=bool(claimed.get("thread")),
            publish=bool(claimed.get("publish")),
            schedule=False,
            analytics=bool(claimed.get("analytics")),
            media_upload=bool(claimed.get("media_upload")),
            listing=bool(claimed.get("listing")),
            listing_edit=bool(claimed.get("listing_edit")),
            listing_delete=bool(claimed.get("listing_delete")),
            handoff=bool(claimed.get("handoff")),
            records=dict(records),
        )

    @classmethod
    def from_serialized(cls, payload: dict[str, Any] | None) -> "SocialProviderCapabilities":
        payload = payload or {}
        if payload and all(isinstance(value, dict) for value in payload.values()):
            records = {
                name: CapabilityRecord(
                    name=name,
                    supported=bool(item.get("supported")),
                    verified=bool(item.get("verified")),
                    verified_at=item.get("verified_at"),
                    method=str(item.get("verification_method") or item.get("method") or "unverified"),
                    verification_method=str(item.get("verification_method") or item.get("method") or "unverified"),
                )
                for name, item in payload.items()
            }
            return cls.from_records(records)
        return cls.from_claimed({name: bool(value) for name, value in payload.items()})

    @classmethod
    def from_claimed(cls, claimed: dict[str, bool], *, verified: bool = False, method: str = "registry_claim") -> "SocialProviderCapabilities":
        records = {
            name: CapabilityRecord(
                name=name,
                supported=bool(value),
                verified=bool(verified and value),
                method=method,
                verification_method=method,
            )
            for name, value in claimed.items()
        }
        return cls(
            text=bool(claimed.get("text")),
            image=bool(claimed.get("image")),
            video=bool(claimed.get("video")),
            carousel=bool(claimed.get("carousel")),
            story=bool(claimed.get("story")),
            reel=bool(claimed.get("reel")),
            thread=bool(claimed.get("thread")),
            publish=bool(claimed.get("publish")),
            schedule=False,
            analytics=bool(claimed.get("analytics")),
            media_upload=bool(claimed.get("media_upload")),
            listing=bool(claimed.get("listing")),
            listing_edit=bool(claimed.get("listing_edit")),
            listing_delete=bool(claimed.get("listing_delete")),
            handoff=bool(claimed.get("handoff")),
            records=records,
        )


@dataclass(frozen=True)
class SocialAccount:
    account_id: str
    provider: str
    platform: str
    username: str = ""
    display_name: str = ""
    avatar_url: str = ""
    status: str = "PENDING"
    capabilities: SocialProviderCapabilities = field(default_factory=SocialProviderCapabilities)
    created_at: str | None = None
    updated_at: str | None = None
    last_verified_at: str | None = None
    credential_ref: str = ""
    region: str = "global"
    provider_account_id: str = ""
    blocked_reason: str | None = None
    channel_id: str = ""
    channel_title: str = ""
    account_type: str = ""
    restriction: str | None = None

    def __post_init__(self) -> None:
        if self.status not in ACCOUNT_STATES:
            raise ValueError(f"invalid account status: {self.status}")
        if not self.created_at:
            object.__setattr__(self, "created_at", _utcnow())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)
        if not self.provider_account_id:
            object.__setattr__(self, "provider_account_id", self.account_id)

    @property
    def id(self) -> str:
        return self.account_id

    @property
    def enabled(self) -> bool:
        return self.status == "ENABLED"

    @property
    def verified(self) -> bool:
        return self.status in {"VERIFIED", "ENABLED"}

    @property
    def account_name(self) -> str:
        return self.display_name or self.username

    @property
    def state(self) -> str:
        return self.status

    @property
    def adapter(self) -> str:
        return self.provider

    @property
    def distribution_backend(self) -> str:
        return "native"

    def as_integration(self) -> Integration:
        return Integration(
            id=self.account_id,
            provider=self.provider,
            account_id=self.account_id,
            region=self.region,
            capabilities=self.capabilities.to_integration(),
            adapter=self.provider,
            distribution_backend="native",
            enabled=self.enabled,
            state="ENABLED" if self.enabled else self.status,
            verified_at=self.last_verified_at,
            account_name=self.account_name,
            platform=self.platform,
        )

    def label(self) -> str:
        handle = f"@{self.username}" if self.username and not self.username.startswith("@") else (self.username or self.account_id)
        return f"{self.platform} {handle}".strip()


def enable_account(account: SocialAccount) -> SocialAccount:
    if account.status != "VERIFIED":
        raise ValueError("only VERIFIED accounts can become ENABLED")
    return transition_account(account, "ENABLED", blocked_reason=None)
