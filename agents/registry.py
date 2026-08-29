"""Runtime agent registry. YAML is inventory; importable implementation is required."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentHandle:
    name: str
    implementation: Any
    owner: str
    capabilities: tuple[str, ...]
    status: str


def _load_yaml() -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyYAML is required to load the agent registry") from exc
    path = Path(__file__).with_name("registry.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _import(path: str) -> Any:
    module_name, _, attr = path.partition(":")
    module = import_module(module_name)
    return getattr(module, attr)


def resolve_agent(name: str) -> AgentHandle:
    agents = (_load_yaml().get("agents") or {})
    spec = agents.get(name)
    if spec is None:
        raise KeyError(name)
    implementation_path = spec.get("implementation")
    if not implementation_path:
        raise RuntimeError(f"{name} is registered without an executable implementation")
    cls = _import(str(implementation_path))
    instance = cls() if callable(cls) else cls
    status = str(spec.get("status") or "inactive")
    if status == "active" and instance is None:
        raise RuntimeError(f"{name} is marked active but has no implementation")
    capabilities = getattr(instance, "capabilities", ())
    if isinstance(capabilities, str):
        capabilities = (capabilities,)
    return AgentHandle(
        name=name,
        implementation=instance,
        owner=str(spec.get("owner") or getattr(instance, "owner", "")),
        capabilities=tuple(capabilities),
        status=status,
    )


def list_agents() -> list[AgentHandle]:
    agents = (_load_yaml().get("agents") or {})
    return [resolve_agent(name) for name in agents]
