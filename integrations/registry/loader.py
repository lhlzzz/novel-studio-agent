"""Dynamic integration registry loader."""

from __future__ import annotations

from pathlib import Path

from integrations.contracts.distribution import Integration, IntegrationCapabilities


def load_registry(path: Path | None = None) -> dict[str, Integration]:
    path = path or Path(__file__).with_name("platforms.yaml")
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyYAML is required to load the integration registry") from exc
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    integrations: dict[str, Integration] = {}
    for provider, config in (raw.get("providers") or {}).items():
        capabilities = IntegrationCapabilities(**(config.get("capabilities") or {}))
        integrations[provider] = Integration(
            id=config.get("id", provider),
            provider=provider,
            account_id=config.get("account_id", ""),
            region=config.get("region", "global"),
            capabilities=capabilities,
            adapter=config.get("adapter", provider),
            distribution_backend=config.get("distribution", "custom"),
            enabled=bool(config.get("enabled", False)),
        )
    return integrations
