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
    return dict(_RUNTIME_STATE.get(provider) or {"state": "REGISTERED", "enabled": False})


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


def clear_runtime_state() -> None:
    _RUNTIME_STATE.clear()


def load_registry(path: Path | None = None) -> dict[str, Integration]:
    path = path or Path(__file__).with_name("platforms.yaml")
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyYAML is required to load the integration registry") from exc
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    integrations: dict[str, Integration] = {}
    for provider, config in (raw.get("providers") or {}).items():
        claimed = _claimed_capabilities(config.get("capabilities") or {})
        runtime = runtime_state(provider)
        capabilities = runtime.get("capabilities") or claimed
        integrations[provider] = Integration(
            id=config.get("id", provider),
            provider=provider,
            account_id=config.get("account_id", ""),
            region=config.get("region", "global"),
            capabilities=capabilities,
            adapter=config.get("adapter", provider),
            distribution_backend=config.get("distribution", "custom"),
            enabled=bool(runtime.get("enabled", False)),
            state=str(runtime.get("state") or "REGISTERED"),
            verified_at=runtime.get("verified_at"),
        )
    return integrations
