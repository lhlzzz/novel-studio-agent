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
    "VERIFIED",
    "ENABLED",
    "DEGRADED",
    "EXPIRED",
    "REVOKED",
    "BLOCKED",
)

ENABLED_FROM = frozenset({"VERIFIED"})


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    records: dict[str, CapabilityRecord] = field(default_factory=dict)

    def verified(self, name: str) -> bool:
        record = self.records.get(name)
        if record is not None:
            return record.allowed
        return bool(getattr(self, name, False))

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
        }

    def to_integration(self) -> IntegrationCapabilities:
        records = dict(self.records)
        for name, supported in self.claimed().items():
            records.setdefault(
                name,
                CapabilityRecord(name=name, supported=supported, verified=False, method="registry_claim"),
            )
        return IntegrationCapabilities(
            publish=self.verified("publish") or self.publish,
            schedule=self.verified("schedule") or self.schedule,
            analytics=self.verified("analytics") or self.analytics,
            media=self.verified("image") or self.verified("video") or self.image or self.video,
            media_upload=self.verified("media_upload") or self.media_upload,
            records=records,
        )

    @classmethod
    def from_claimed(cls, claimed: dict[str, bool], *, verified: bool = False, method: str = "registry_claim") -> "SocialProviderCapabilities":
        records = {
            name: CapabilityRecord(name=name, supported=bool(value), verified=bool(verified and value), method=method)
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
            schedule=bool(claimed.get("schedule")),
            analytics=bool(claimed.get("analytics")),
            media_upload=bool(claimed.get("media_upload")),
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
    return replace(account, status="ENABLED", updated_at=_utcnow())
