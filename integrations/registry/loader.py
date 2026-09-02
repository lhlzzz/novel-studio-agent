"""Dynamic integration registry loader.

YAML may register providers. It may not mark them enabled.
Enabled is a runtime verification state, never a config flag.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from integrations.contracts.distribution import (
    CapabilityRecord,
    Integration,
    IntegrationCapabilities,
)
from social.providers.registry import (
    clear_runtime_state as clear_social_runtime_state,
    load_social_registry,
    runtime_state as social_runtime_state,
    set_runtime_state as set_social_runtime_state,
)

_RUNTIME_STATE: dict[str, dict[str, Any]] = {}


def _claimed_capabilities(raw: dict[str, Any] | None) -> IntegrationCapabilities:
    claimed = dict(raw or {})
    records = {
        name: CapabilityRecord(name=name, supported=bool(value), verified=False, method="registry_claim")
        for name, value in claimed.items()
        if name != "records"
    }
    return IntegrationCapabilities(records=records)


def runtime_state(provider: str) -> dict[str, Any]:
    return dict(_RUNTIME_STATE.get(provider) or social_runtime_state(provider) or {"state": "REGISTERED", "enabled": False})


def set_runtime_state(
    provider: str,
    *,
    state: str,
    enabled: bool = False,
    verified_at: str | None = None,
    capabilities: IntegrationCapabilities | None = None,
) -> None:
    _RUNTIME_STATE[provider] = {
        "state": state,
        "enabled": bool(enabled and state == "ENABLED"),
        "verified_at": verified_at,
        "capabilities": capabilities,
    }
    set_social_runtime_state(provider, state=state, enabled=enabled, verified_at=verified_at)


def clear_runtime_state() -> None:
    _RUNTIME_STATE.clear()
    clear_social_runtime_state()


def load_registry(path: Path | None = None) -> dict[str, Integration]:
    social = load_social_registry(path)
    integrations: dict[str, Integration] = {}
    for provider, registration in social.items():
        runtime = runtime_state(provider)
        capabilities = runtime.get("capabilities") or registration.capabilities.to_integration()
        integrations[provider] = Integration(
            id=registration.id,
            provider=provider,
            account_id="",
            region=registration.region,
            capabilities=capabilities,
            adapter=registration.adapter,
            distribution_backend=registration.distribution_backend,
            enabled=bool(runtime.get("enabled", False)),
            state=str(runtime.get("state") or registration.state or "REGISTERED"),
            verified_at=runtime.get("verified_at"),
            platform=registration.platform,
        )
    return integrations
