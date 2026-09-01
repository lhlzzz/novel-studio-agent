"""Provider cost persistence. Run totals are derived, not the only record."""

from __future__ import annotations

from creative.schemas import GenerationUsage


class CostEngine:
    def __init__(self, store) -> None:
        self.store = store

    def record(self, usage: GenerationUsage) -> None:
        self.store.save_usage(usage)
