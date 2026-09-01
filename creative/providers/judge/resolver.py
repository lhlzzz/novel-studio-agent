"""Resolve a vision judge provider. Production never auto-falls back to mock."""

from __future__ import annotations

from typing import Any

from creative.errors import JudgeBlocked, ProviderBlocked


class VisionJudgeResolver:
    def __init__(self, *, providers: dict[str, Any] | None = None, allow_mock: bool = False) -> None:
        self.allow_mock = allow_mock
        self.providers = dict(providers) if providers is not None else {}
        if allow_mock and "mock-vision" not in self.providers:
            from creative.providers.judge.mock import MockVisionJudgeProvider
            self.providers["mock-vision"] = MockVisionJudgeProvider()
        if providers is None and not allow_mock and "ai-gateway" not in self.providers:
            from creative.providers.judge.gateway import GatewayVisionProvider
            self.providers["ai-gateway"] = GatewayVisionProvider()

    def resolve(self):
        if self.allow_mock:
            provider = self.providers.get("mock-vision")
            if provider is not None:
                return provider
        for name, provider in self.providers.items():
            if name == "mock-vision":
                continue
            ready = getattr(provider, "live_ready", None)
            if callable(ready):
                ok, reason = ready()
                if ok:
                    return provider
                raise ProviderBlocked(name, reason)
            return provider
        if self.allow_mock and "mock-vision" in self.providers:
            return self.providers["mock-vision"]
        raise JudgeBlocked("no verified vision provider")
