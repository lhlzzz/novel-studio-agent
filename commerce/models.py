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
