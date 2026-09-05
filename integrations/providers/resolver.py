"""Resolve providers and adapters without hard-coding them in agents.

Social routing and creative routing stay separate. Creative never publishes.
Social never generates media.
"""

from __future__ import annotations

from typing import Any

from social.providers.resolver import (
    ADAPTER_IMPORTS,
    PROVIDER_CAPABILITIES,
    ProviderHandle,
    provider_surface,
    resolve_adapter,
    resolve_capability,
    resolve_provider,
    resolve_social_provider,
)


def resolve_creative_provider(name: str = "lechuang", *, requirement: dict[str, Any] | None = None, allow_mock: bool = False):
    """Resolve a generation provider. Does not route social publish adapters."""
    from creative.providers.resolver import GenerationProviderResolver

    resolver = GenerationProviderResolver(allow_mock=allow_mock)
    return resolver.resolve(name, requirement=requirement)


def select_creative_provider(requirement: dict[str, Any], *, history: list[dict[str, Any]] | None = None, allow_mock: bool = False):
    from creative.providers.resolver import GenerationProviderResolver

    resolver = GenerationProviderResolver(allow_mock=allow_mock)
    return resolver.select(requirement, history=history)


__all__ = [
    "ADAPTER_IMPORTS",
    "PROVIDER_CAPABILITIES",
    "ProviderHandle",
    "provider_surface",
    "resolve_adapter",
    "resolve_capability",
    "resolve_creative_provider",
    "resolve_provider",
    "resolve_social_provider",
    "select_creative_provider",
]
