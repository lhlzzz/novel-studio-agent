"""Lechuang-facing shapes. No guessed request fields are treated as live."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LechuangAuth:
    base_url: str
    api_key_present: bool
    contract_verified: bool
    reason: str


@dataclass(frozen=True)
class LechuangCapability:
    name: str
    claimed: bool
    verified: bool
    async_mode: bool = True
    reason: str = ""


@dataclass(frozen=True)
class LechuangTaskView:
    provider_task_id: str
    status: str
    raw: dict[str, Any] = field(default_factory=dict)
