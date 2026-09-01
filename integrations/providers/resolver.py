"""Resolve providers and adapters without hard-coding them in DistributionAgent."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from integrations.adapters.unsupported import UnsupportedDistributionAdapter
from integrations.contracts.distribution import (
    CapabilityRecord,
    Integration,
    IntegrationCapabilities,
)
from integrations.registry.loader import load_registry

ADAPTER_IMPORTS = {
    "postiz": "integrations.providers.postiz.adapter:PostizAdapter",
}

PROVIDER_CAPABILITIES = {
    "postiz": {
        "publish": {"api": True, "mcp": True},
        "schedule": {"api": True, "mcp": True},
        "upload": {"api": True, "mcp": False},
        "media_upload": {"api": True, "mcp": False},
        "analytics": {"api": True, "mcp": False},
        "integration_list": {"api": True, "mcp": True},
        "integration_settings": {"api": True, "mcp": True},
    }
}


@dataclass(frozen=True)
class ProviderHandle:
    name: str
    owner: str
    adapter_name: str
    implementation: Any
    status: str
    capabilities: IntegrationCapabilities
    integration: Integration | None


def _load_class(path: str):
    module_name, _, class_name = path.partition(":")
    module = import_module(module_name)
    return getattr(module, class_name)


def resolve_provider(provider_name: str, *, adapter: Any | None = None) -> ProviderHandle:
    registry = load_registry()
    integration = registry.get(provider_name)
    if integration is None:
        raise KeyError(f"unknown provider: {provider_name}")
    adapter_path = ADAPTER_IMPORTS.get(integration.adapter)
    if adapter is None:
        if adapter_path is None:
            implementation = UnsupportedDistributionAdapter(integration)
        else:
            implementation = _load_class(adapter_path)()
    else:
        implementation = adapter
    status = "enabled" if integration.enabled else integration.state.lower()
    return ProviderHandle(
        name=provider_name,
        owner="integrations",
        adapter_name=integration.adapter,
        implementation=implementation,
        status=status,
        capabilities=integration.capabilities,
        integration=integration,
    )


def resolve_integration(integration_id: str, *, adapter: Any | None = None) -> ProviderHandle:
    """Resolve an account integration to its registered provider adapter."""
    registry = load_registry()
    integration = next((item for item in registry.values() if item.id == integration_id), None)
    if integration is None:
        raise KeyError(f"unknown integration: {integration_id}")
    return resolve_provider(integration.provider, adapter=adapter)


def resolve_adapter(integration_id: str, *, adapter: Any | None = None, registry: dict[str, Integration] | None = None):
    if adapter is not None:
        return adapter
    registry = registry or load_registry()
    for integration in registry.values():
        if integration.id == integration_id:
            return resolve_provider(integration.provider).implementation
    raise KeyError(f"no adapter registered for integration_id={integration_id}")


def resolve_capability(integration_id: str, capability: str, *, adapter: Any | None = None) -> CapabilityRecord:
    if adapter is None:
        registry = load_registry()
        integration = registry.get(integration_id) or next(
            (item for item in registry.values() if item.id == integration_id),
            None,
        )
        if integration is not None:
            records = integration.capabilities.records or {}
            if capability in records:
                return records[capability]
            return CapabilityRecord(
                name=capability,
                supported=bool(getattr(integration.capabilities, capability, False)),
                verified=False,
                method="registry_claim",
            )
    implementation = resolve_adapter(integration_id, adapter=adapter)
    get_capabilities = getattr(implementation, "get_capabilities", None)
    if get_capabilities is None:
        return CapabilityRecord(name=capability, supported=False, verified=False, method="missing_adapter")
    capabilities = get_capabilities(integration_id)
    records = getattr(capabilities, "records", {}) or {}
    if capability in records:
        return records[capability]
    supported = bool(getattr(capabilities, capability, False))
    return CapabilityRecord(
        name=capability,
        supported=supported,
        verified=supported,
        method="adapter_boolean",
    )


def provider_surface(provider_name: str, capability: str) -> str:
    spec = (PROVIDER_CAPABILITIES.get(provider_name) or {}).get(capability) or {}
    api = bool(spec.get("api"))
    mcp = bool(spec.get("mcp"))
    if api and mcp:
        return "both"
    if mcp:
        return "mcp_only"
    if api:
        return "api_only"
    return "none"
