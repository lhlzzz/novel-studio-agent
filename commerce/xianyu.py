"""Xianyu listing is a commerce distribution surface, not a social post."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class XianyuListingPackage:
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

    def __post_init__(self) -> None:
        if self.commerce_intent in {"", "none"}:
            raise ValueError("Xianyu listing requires explicit commerce intent")
