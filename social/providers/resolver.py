"""SocialProviderResolver is the only native social routing mechanism."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from integrations.adapters.unsupported import UnsupportedDistributionAdapter
from integrations.contracts.distribution import CapabilityRecord, Integration, IntegrationCapabilities
from social.providers.registry import load_social_registry

ADAPTER_IMPORTS = {
    "x": "social.providers.x.adapter:XAdapter",
    "instagram": "social.providers.instagram.adapter:InstagramAdapter",
    "youtube": "social.providers.youtube.adapter:YouTubeAdapter",
    "tiktok": "social.providers.tiktok.adapter:TikTokAdapter",
    "linkedin": "social.providers.linkedin.adapter:LinkedInAdapter",
}

PROVIDER_CAPABILITIES = {
    "x": {
        "text": {"api": True, "mcp": False},
        "image": {"api": True, "mcp": False},
        "video": {"api": True, "mcp": False},
        "thread": {"api": True, "mcp": False},
        "publish": {"api": True, "mcp": False},
        "media_upload": {"api": True, "mcp": False},
        "analytics": {"api": True, "mcp": False},
        "schedule": {"api": False, "mcp": False},
        "carousel": {"api": False, "mcp": False},
        "story": {"api": False, "mcp": False},
        "reel": {"api": False, "mcp": False},
    },
    "instagram": {
        "image": {"api": True, "mcp": False},
        "video": {"api": True, "mcp": False},
        "reel": {"api": True, "mcp": False},
        "carousel": {"api": True, "mcp": False},
        "publish": {"api": True, "mcp": False},
        "text": {"api": False, "mcp": False},
        "thread": {"api": False, "mcp": False},
        "story": {"api": True, "mcp": False},
        "schedule": {"api": False, "mcp": False},
        "analytics": {"api": True, "mcp": False},
        "media_upload": {"api": True, "mcp": False},
    },
    "youtube": {
        "video": {"api": True, "mcp": False},
        "publish": {"api": True, "mcp": False},
        "analytics": {"api": True, "mcp": False},
        "media_upload": {"api": True, "mcp": False},
        "text": {"api": False, "mcp": False},
        "image": {"api": False, "mcp": False},
        "carousel": {"api": False, "mcp": False},
        "story": {"api": False, "mcp": False},
        "reel": {"api": False, "mcp": False},
        "thread": {"api": False, "mcp": False},
        "schedule": {"api": False, "mcp": False},
    },
    "tiktok": {
        "video": {"api": True, "mcp": False},
        "publish": {"api": True, "mcp": False},
        "analytics": {"api": True, "mcp": False},
        "media_upload": {"api": True, "mcp": False},
        "text": {"api": False, "mcp": False},
        "image": {"api": False, "mcp": False},
        "carousel": {"api": False, "mcp": False},
        "story": {"api": False, "mcp": False},
        "reel": {"api": False, "mcp": False},
        "thread": {"api": False, "mcp": False},
        "schedule": {"api": False, "mcp": False},
    },
    "linkedin": {
        "text": {"api": True, "mcp": False},
        "image": {"api": True, "mcp": False},
        "video": {"api": True, "mcp": False},
        "publish": {"api": True, "mcp": False},
        "analytics": {"api": True, "mcp": False},
        "media_upload": {"api": True, "mcp": False},
        "carousel": {"api": False, "mcp": False},
        "story": {"api": False, "mcp": False},
        "reel": {"api": False, "mcp": False},
        "thread": {"api": False, "mcp": False},
        "schedule": {"api": False, "mcp": False},
    },
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


def resolve_social_provider(provider_name: str, *, adapter: Any | None = None) -> ProviderHandle:
    registry = load_social_registry()
    registration = registry.get(provider_name)
    if registration is None:
        raise KeyError(f"unknown provider: {provider_name}")
    adapter_path = ADAPTER_IMPORTS.get(registration.adapter)
    if adapter is None:
        if adapter_path is None:
            integration = Integration(
                id=registration.name,
                provider=registration.name,
                account_id="",
                region=registration.region,
                capabilities=registration.capabilities.to_integration(),
                adapter=registration.adapter,
                distribution_backend=registration.distribution_backend,
                enabled=False,
                state=registration.state,
                platform=registration.platform,
            )
            implementation = UnsupportedDistributionAdapter(integration)
        else:
            implementation = _load_class(adapter_path)()
    else:
        implementation = adapter
    status = "enabled" if registration.enabled else registration.state.lower()
    integration = Integration(
        id=registration.name,
        provider=registration.name,
        account_id="",
        region=registration.region,
        capabilities=registration.capabilities.to_integration(),
        adapter=registration.adapter,
        distribution_backend=registration.distribution_backend,
        enabled=registration.enabled,
        state="ENABLED" if registration.enabled else registration.state,
        platform=registration.platform,
    )
    return ProviderHandle(
        name=provider_name,
        owner="social",
        adapter_name=registration.adapter,
        implementation=implementation,
        status=status,
        capabilities=integration.capabilities,
        integration=integration,
    )


def resolve_provider(provider_name: str, *, adapter: Any | None = None) -> ProviderHandle:
    return resolve_social_provider(provider_name, adapter=adapter)


def resolve_adapter(integration_id: str, *, adapter: Any | None = None, registry: dict | None = None):
    if adapter is not None:
        return adapter
    registry = registry or load_social_registry()
    if integration_id in registry:
        return resolve_social_provider(integration_id).implementation
    for registration in registry.values():
        if registration.id == integration_id or registration.adapter == integration_id:
            return resolve_social_provider(registration.name).implementation
    raise KeyError(f"no adapter registered for integration_id={integration_id}")


def resolve_capability(integration_id: str, capability: str, *, adapter: Any | None = None) -> CapabilityRecord:
    if adapter is None:
        registry = load_social_registry()
        registration = registry.get(integration_id)
        if registration is not None:
            records = registration.capabilities.records or {}
            if capability in records:
                return records[capability]
            return CapabilityRecord(
                name=capability,
                supported=bool(getattr(registration.capabilities, capability, False)),
                verified=False,
                method="registry_claim",
            )
    implementation = resolve_adapter(integration_id, adapter=adapter)
    get_capabilities = getattr(implementation, "capabilities", None) or getattr(implementation, "get_capabilities", None)
    if get_capabilities is None:
        return CapabilityRecord(name=capability, supported=False, verified=False, method="missing_adapter")
    capabilities = get_capabilities(integration_id)
    records = getattr(capabilities, "records", {}) or {}
    if capability in records:
        return records[capability]
    supported = bool(getattr(capabilities, capability, False))
    return CapabilityRecord(name=capability, supported=supported, verified=supported, method="adapter_boolean")


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
