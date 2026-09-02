"""Xianyu listing is a first-class commerce entity, not a social post."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from typing import Any

LISTING_STATES = (
    "DRAFT",
    "SUBMITTING",
    "PROCESSING",
    "ONLINE",
    "FAILED",
    "REMOVED",
    "UNKNOWN",
)

LISTING_TRANSITIONS = {
    "DRAFT": {"SUBMITTING", "FAILED", "UNKNOWN"},
    "SUBMITTING": {"PROCESSING", "FAILED", "UNKNOWN"},
    "PROCESSING": {"ONLINE", "FAILED", "UNKNOWN"},
    "ONLINE": {"REMOVED", "FAILED", "UNKNOWN"},
    "FAILED": {"DRAFT", "SUBMITTING"},
    "REMOVED": set(),
    "UNKNOWN": {"PROCESSING", "ONLINE", "FAILED", "REMOVED"},
}


class IllegalListingTransition(ValueError):
    """Raised when a listing cannot move to the requested status."""


def map_listing_status(raw: str) -> str:
    value = str(raw or "").lower()
    if value in {"0", "online", "onsale", "published", "sale", "online_success"}:
        return "ONLINE"
    if value in {"1", "offline", "downshelf", "instock", "removed"}:
        return "REMOVED"
    if value in {"2", "deleted", "delete"}:
        return "REMOVED"
    if value in {"3", "reviewing", "audit", "pending", "processing", "submitted"}:
        return "PROCESSING"
    if value in {"4", "blocked", "punish", "failed", "fail"}:
        return "FAILED"
    if value in {"draft"}:
        return "DRAFT"
    if value in {"submitting"}:
        return "SUBMITTING"
    if value in {"unknown"}:
        return "UNKNOWN"
    return "UNKNOWN"


def transition_listing(listing: "XianyuListing", new_status: str, **changes: Any) -> "XianyuListing":
    if new_status not in LISTING_STATES:
        raise ValueError(f"invalid listing status: {new_status}")
    allowed = LISTING_TRANSITIONS.get(listing.status, set())
    if new_status != listing.status and new_status not in allowed:
        raise IllegalListingTransition(f"{listing.status} -> {new_status} is not allowed")
    return replace(listing, status=new_status, **changes)


def _validate_price(price: str | int | float | Decimal) -> str:
    try:
        value = Decimal(str(price))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Xianyu listing price must be a number > 0") from exc
    if value <= 0:
        raise ValueError("Xianyu listing price must be > 0")
    return format(value, "f")


@dataclass(frozen=True)
class XianyuListing:
    listing_id: str
    account_id: str
    title: str
    description: str
    price: str
    quantity: int = 1
    category_id: str = ""
    images: tuple[str, ...] = ()
    cover: str | None = None
    condition: str = "new"
    location: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    shipping: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    commerce_intent: str = "explicit"
    status: str = "DRAFT"
    provider_item_id: str = ""
    distribution_job_id: str = ""
    content_package_id: str = ""
    provider_response: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.commerce_intent in {"", "none"}:
            raise ValueError("Xianyu listing requires explicit commerce intent")
        if not str(self.title or "").strip():
            raise ValueError("Xianyu listing title is required")
        if not str(self.category_id or "").strip():
            raise ValueError("Xianyu listing category_id is required")
        object.__setattr__(self, "price", _validate_price(self.price))
        if int(self.quantity) < 1:
            raise ValueError("Xianyu listing quantity must be >= 1")
        object.__setattr__(self, "quantity", int(self.quantity))
        if self.status not in LISTING_STATES:
            raise ValueError(f"invalid listing status: {self.status}")
        for image in self.images:
            if str(image).startswith("/") or str(image).startswith("."):
                raise ValueError("Xianyu listing images must be provider media identifiers, not local paths")

