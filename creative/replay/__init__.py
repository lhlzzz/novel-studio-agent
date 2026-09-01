"""Replay binds a new run to an immutable workflow version and original inputs."""

from __future__ import annotations

from typing import Any


class ReplayEngine:
    def __init__(self, engine) -> None:
        self.engine = engine

    def replay(self, run_id: str, **kwargs: Any):
        return self.engine.replay(run_id, **kwargs)
