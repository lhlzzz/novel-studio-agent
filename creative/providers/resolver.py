"""Match a creative requirement to a generation provider. Never hard-code Lechuang as destiny."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from creative.errors import ProviderBlocked, UnsupportedCapability
from creative.providers.lechuang.adapter import LechuangAdapter
from creative.providers.mock import MockGenerationProvider

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

REGISTRY_PATH = Path(__file__).with_name("capabilities") / "registry.yaml"


@dataclass(frozen=True)
class ModelCapability:
    provider: str
    model: str
    input_types: tuple[str, ...]
    output_types: tuple[str, ...]
    supported_references: tuple[str, ...]
    resolution: tuple[str, ...]
    aspect_ratio: tuple[str, ...]
    duration: tuple[str, ...]
    async_mode: bool
    verified: bool
    capabilities: tuple[str, ...]


def load_capability_registry(path: Path | None = None) -> list[ModelCapability]:
    path = path or REGISTRY_PATH
    if yaml is None or not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = []
    for item in raw.get("models") or []:
        items.append(ModelCapability(
            provider=str(item.get("provider") or ""),
            model=str(item.get("model") or ""),
            input_types=tuple(item.get("input_types") or ()),
            output_types=tuple(item.get("output_types") or ()),
            supported_references=tuple(item.get("supported_references") or ()),
            resolution=tuple(item.get("resolution") or ()),
            aspect_ratio=tuple(item.get("aspect_ratio") or ()),
            duration=tuple(str(x) for x in (item.get("duration") or ())),
            async_mode=bool(item.get("async", True)),
            verified=bool(item.get("verified", False)),
            capabilities=tuple(item.get("capabilities") or ()),
        ))
    return items


def match_capabilities(requirement: dict[str, Any], registry: list[ModelCapability] | None = None) -> list[ModelCapability]:
    registry = registry if registry is not None else load_capability_registry()
    need_in = set(requirement.get("input_types") or [])
    need_out = set(requirement.get("output_types") or [])
    aspect = str(requirement.get("aspect_ratio") or "")
    capability = str(requirement.get("capability") or "")
    hits = []
    for item in registry:
        if need_in and not need_in.issubset(item.input_types) and need_in - set(item.input_types):
            if not any(token in item.input_types for token in need_in):
                continue
        if need_out and not any(token in item.output_types for token in need_out):
            continue
        if aspect and item.aspect_ratio and aspect not in item.aspect_ratio:
            continue
        if capability and item.capabilities and capability not in item.capabilities:
            continue
        hits.append(item)
    return hits


class GenerationProviderResolver:
    def __init__(self, *, providers: dict[str, Any] | None = None, allow_mock: bool = False) -> None:
        self.allow_mock = allow_mock
        self.providers = dict(providers or {})
        if "lechuang" not in self.providers:
            self.providers["lechuang"] = LechuangAdapter()
        if "mock" not in self.providers:
            self.providers["mock"] = MockGenerationProvider()

    def resolve(self, name: str, *, requirement: dict[str, Any] | None = None):
        if name == "lechuang":
            adapter = self.providers["lechuang"]
            live_ready = getattr(adapter, "live_ready", None)
            if not callable(live_ready):
                return adapter, getattr(adapter, "name", name)
            ready, reason = live_ready()
            if ready:
                return adapter, "lechuang"
            if self.allow_mock:
                return self.providers["mock"], "mock"
            raise ProviderBlocked("lechuang", reason)
        if name not in self.providers:
            raise UnsupportedCapability(name, provider="resolver")
        return self.providers[name], name

    def select(self, requirement: dict[str, Any]) -> tuple[Any, ModelCapability | None]:
        matches = match_capabilities(requirement)
        live = [item for item in matches if item.verified]
        chosen = (live or matches or [None])[0]
        provider_name = chosen.provider if chosen else str(requirement.get("provider") or "lechuang")
        implementation, resolved = self.resolve(provider_name, requirement=requirement)
        return implementation, chosen
