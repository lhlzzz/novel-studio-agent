"""Match a creative requirement to Lechuang. Mock is tests only."""

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


class ProviderRanker:
    def rank(self, matches: list[ModelCapability], *, requirement: dict[str, Any] | None = None, history: list[dict[str, Any]] | None = None) -> list[ModelCapability]:
        requirement = requirement or {}
        history = history or []
        preferred = str(requirement.get("provider") or requirement.get("user_preference") or "")
        policy = dict(requirement.get("workflow_policy") or {})
        scored = []
        for item in matches:
            quality = _history_score(history, item, "quality_score", 50)
            cost = _history_score(history, item, "cost", 5)
            latency = _history_score(history, item, "latency", 20)
            score = 0.0
            score += 40 if item.verified else 0
            score += 15 if requirement.get("capability") in item.capabilities else 5
            score += min(quality, 100) * 0.2
            score -= min(cost, 50) * 0.15
            score -= min(latency, 120) * 0.05
            if preferred and item.provider == preferred:
                score += 12
            if policy.get("provider") == item.provider:
                score += 8
            availability = 10 if item.verified else 0
            score += availability
            success = _history_score(history, item, "success_rate", 50)
            score += min(success, 100) * 0.1
            node_type = str(requirement.get("node_type") or "")
            if node_type and (node_type in item.capabilities or node_type in item.output_types):
                score += 6
            workflow = str(requirement.get("workflow") or requirement.get("workflow_id") or "")
            if workflow and policy.get("workflow") == workflow:
                score += 4
            content_type = str(requirement.get("content_type") or "")
            if content_type and content_type in item.output_types:
                score += 5
            health_map = dict(requirement.get("health") or {})
            if item.provider in health_map:
                score += 10 if health_map[item.provider] else -20
            else:
                score += 10 if item.verified else 0
            scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored]


def _history_score(history: list[dict[str, Any]], item: ModelCapability, field: str, default: float) -> float:
    rows = [row for row in history if row.get("provider") == item.provider or row.get("model") == item.model]
    if not rows:
        return default
    return sum(float(row.get(field) or default) for row in rows) / len(rows)


class GenerationProviderResolver:
    def __init__(self, *, providers: dict[str, Any] | None = None, allow_mock: bool = False, ranker: ProviderRanker | None = None) -> None:
        self.allow_mock = allow_mock
        self.providers = dict(providers or {})
        self.ranker = ranker or ProviderRanker()
        if "lechuang" not in self.providers:
            self.providers["lechuang"] = LechuangAdapter()
        self.providers.pop("xai", None)
        if allow_mock and "mock" not in self.providers:
            self.providers["mock"] = MockGenerationProvider()
        if not allow_mock and "mock" not in (providers or {}):
            self.providers.pop("mock", None)

    def resolve(self, name: str, *, requirement: dict[str, Any] | None = None):
        if name in {"lechuang", "xiaole", "xiaoleai", "xai"}:
            adapter = self.providers.get("lechuang") or self.providers.get(name)
            if adapter is None:
                raise UnsupportedCapability(name, provider="resolver")
            live_ready = getattr(adapter, "live_ready", None)
            if not callable(live_ready):
                return adapter, getattr(adapter, "name", "lechuang")
            ready, reason = live_ready()
            if ready:
                return adapter, "lechuang"
            if self.allow_mock:
                return self.providers["mock"], "mock"
            raise ProviderBlocked("lechuang", reason)
        if name == "mock" and not self.allow_mock:
            raise ProviderBlocked("mock", "mock is tests only")
        if name not in self.providers:
            raise UnsupportedCapability(name, provider="resolver")
        return self.providers[name], name

    def select(self, requirement: dict[str, Any], *, history: list[dict[str, Any]] | None = None) -> tuple[Any, ModelCapability | None]:
        matches = match_capabilities(requirement)
        ranked = self.ranker.rank(matches, requirement=requirement, history=history)
        live = [item for item in ranked if item.verified]
        chosen = (live or ranked or [None])[0]
        if chosen is not None and not chosen.verified and not self.allow_mock:
            raise ProviderBlocked(chosen.provider, f"{chosen.model} unverified")
        provider_name = chosen.provider if chosen else str(requirement.get("provider") or "lechuang")
        if provider_name in {"xiaole", "xiaoleai", "xai"}:
            provider_name = "lechuang"
        if provider_name == "mock" and not self.allow_mock:
            raise ProviderBlocked("mock", "mock is tests only")
        implementation, resolved = self.resolve(provider_name, requirement=requirement)
        return implementation, chosen
