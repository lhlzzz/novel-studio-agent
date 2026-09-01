"""Render graph operations. Output is always a new file."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RENDER_OPS = ("trim", "concat", "resize", "fps", "audio", "mute", "subtitle", "merge", "export")


@dataclass(frozen=True)
class RenderOp:
    op: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderPlan:
    inputs: tuple[str, ...]
    ops: tuple[RenderOp, ...] = ()
    output_name: str = "export"
