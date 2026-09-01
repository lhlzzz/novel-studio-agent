"""Judge registry and regeneration policy."""

from __future__ import annotations

from typing import Any

from creative.errors import JudgeBlocked, ProviderBlocked
from creative.judges.consistency import ConsistencyJudge
from creative.judges.content import ContentFitJudge
from creative.judges.policy import ContentPolicyGate
from creative.judges.technical import TechnicalQA
from creative.judges.video import VideoJudge
from creative.judges.vision import ImageJudge
from creative.providers.judge.resolver import VisionJudgeResolver
from creative.schemas import JudgeResult, MediaAsset, REGENERATION_STRATEGIES


class RegenerationStrategy:
    def next_action(self, attempt: int, *, last: JudgeResult | None = None, max_regenerations: int | None = None) -> str:
        limit = max_regenerations if max_regenerations is not None else len(REGENERATION_STRATEGIES)
        if attempt >= limit or attempt >= len(REGENERATION_STRATEGIES):
            return "stop"
        return REGENERATION_STRATEGIES[attempt]


def rank_assets(pairs: list[tuple[MediaAsset, JudgeResult]]) -> list[tuple[MediaAsset, JudgeResult]]:
    return sorted(pairs, key=lambda item: item[1].score, reverse=True)


def bind_judges(provider=None) -> dict[str, Any]:
    return {
        "image": ImageJudge(provider),
        "video": VideoJudge(provider),
        "consistency": ConsistencyJudge(provider),
        "identity": ConsistencyJudge(provider),
        "content_fit": ContentFitJudge(provider),
        "continuity": ConsistencyJudge(provider),
        "policy": ContentPolicyGate(),
        "technical": TechnicalQA(),
    }


class JudgeRegistry:
    def __init__(self, *, allow_mock: bool = False, resolver: VisionJudgeResolver | None = None) -> None:
        self.allow_mock = allow_mock
        self.resolver = resolver or VisionJudgeResolver(allow_mock=allow_mock)

    def resolve(self):
        try:
            return self.resolver.resolve()
        except (JudgeBlocked, ProviderBlocked):
            if self.allow_mock:
                from creative.providers.judge.mock import MockVisionJudgeProvider
                return MockVisionJudgeProvider()
            raise

    def bind(self, provider=None) -> dict[str, Any]:
        return bind_judges(provider)


JUDGES = bind_judges()
