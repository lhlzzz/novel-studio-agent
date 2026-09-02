"""Commerce objects are separate from content objects."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContentProductLink:
    content_package_id: str
    product_id: str
    relation: str = "supports"


@dataclass(frozen=True)
class CommerceDecision:
    """Explicit commerce decision. ContentPackage.commerce_intent never creates a listing by itself."""

    intent: str = "none"
    source: str = "strategy"

    def allows_listing(self) -> bool:
        return self.intent not in {"", "none"}

