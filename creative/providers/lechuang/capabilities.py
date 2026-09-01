"""Claimed vs verified Lechuang capabilities. YAML never enables live generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from creative.providers.lechuang.schemas import LechuangCapability

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

MODELS_PATH = Path(__file__).with_name("models.yaml")


def load_models(path: Path | None = None) -> dict[str, Any]:
    path = path or MODELS_PATH
    if yaml is None:
        return {"contract": {"verified": False}, "models": {}}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def claimed_capabilities() -> list[LechuangCapability]:
    data = load_models()
    verified_contract = bool((data.get("contract") or {}).get("verified"))
    reason = str((data.get("contract") or {}).get("reason") or "")
    items = []
    seen: set[str] = set()
    for model_id, spec in (data.get("models") or {}).items():
        for name in spec.get("capabilities") or []:
            if name in seen:
                continue
            seen.add(name)
            items.append(LechuangCapability(
                name=str(name),
                claimed=True,
                verified=bool(spec.get("verified") and verified_contract),
                async_mode=bool(spec.get("async", True)),
                reason="" if verified_contract else reason,
            ))
    return items
