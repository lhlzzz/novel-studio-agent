"""Resolve providers and adapters without hard-coding them in DistributionAgent."""

from __future__ import annotations

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

__all__ = [
    "ADAPTER_IMPORTS",
    "PROVIDER_CAPABILITIES",
    "ProviderHandle",
    "provider_surface",
    "resolve_adapter",
    "resolve_capability",
    "resolve_provider",
    "resolve_social_provider",
]
