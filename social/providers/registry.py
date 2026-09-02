"""SocialProviderRegistry: YAML may register, runtime verification enables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from social.accounts.models import SocialProviderCapabilities

_RUNTIME_STATE: dict[str, dict[str, Any]] = {}

CN_PROVIDERS = ("xiaohongshu", "douyin", "kuaishou", "xianyu")
OVERSEAS_PROVIDERS = ("x", "instagram", "youtube", "tiktok", "linkedin")
NATIVE_PROVIDERS = CN_PROVIDERS



@dataclass(frozen=True)
class SocialProviderRegistration:
    name: str
    platform: str
    adapter: str
    region: str
    capabilities: SocialProviderCapabilities
    state: str = "REGISTERED"
    enabled: bool = False
    verified_at: str | None = None
    distribution_backend: str = "native"

    @property
    def id(self) -> str:
        return self.name

    @property
    def provider(self) -> str:
        return self.name


def runtime_state(provider: str) -> dict[str, Any]:
    return dict(_RUNTIME_STATE.get(provider) or {"state": "REGISTERED", "enabled": False})


def set_runtime_state(
    provider: str,
    *,
    state: str,
    enabled: bool = False,
    verified_at: str | None = None,
    capabilities: SocialProviderCapabilities | None = None,
) -> None:
    _RUNTIME_STATE[provider] = {
        "state": state,
        "enabled": bool(enabled and state == "ENABLED"),
        "verified_at": verified_at,
        "capabilities": capabilities,
    }


def clear_runtime_state() -> None:
    _RUNTIME_STATE.clear()


def load_social_registry(path: Path | None = None) -> dict[str, SocialProviderRegistration]:
    path = path or Path(__file__).resolve().parents[2] / "integrations/registry/platforms.yaml"
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyYAML is required to load the social provider registry") from exc
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    registry: dict[str, SocialProviderRegistration] = {}
    for provider, config in (raw.get("providers") or {}).items():
        if bool(config.get("enabled")):
            raise ValueError(f"{provider}: YAML must not set enabled: true")
        claimed = SocialProviderCapabilities.from_claimed(config.get("capabilities") or {})
        runtime = runtime_state(provider)
        capabilities = runtime.get("capabilities") or claimed
        state = str(runtime.get("state") or "REGISTERED")
        registry[provider] = SocialProviderRegistration(
            name=provider,
            platform=str(config.get("platform") or provider),
            adapter=str(config.get("adapter") or provider),
            region=str(config.get("region") or "global"),
            capabilities=capabilities,
            state=state,
            enabled=bool(runtime.get("enabled", False)),
            verified_at=runtime.get("verified_at"),
            distribution_backend=str(config.get("distribution") or "native"),
        )
    return registry
