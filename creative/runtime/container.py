"""Unique composition root for creative production runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from creative.assets import AssetStore
from creative.cost import CostEngine
from creative.idempotency import IdempotencyKey
from creative.judges.registry import JudgeRegistry
from creative.providers.resolver import GenerationProviderResolver
from creative.replay import ReplayEngine
from creative.store import CreativeStore
from creative.workflow.engine import CreativeWorkflowEngine
from creative.workflow.registry import list_workflows, load_from_store, load_templates, resolve_workflow
from creative.workflow.resolver import WorkflowResolver


@dataclass
class CreativeRuntime:
    store: CreativeStore
    assets: AssetStore
    workflow_registry: Any
    workflow_resolver: WorkflowResolver
    provider_resolver: GenerationProviderResolver
    engine: CreativeWorkflowEngine
    judge_registry: JudgeRegistry
    cost_engine: CostEngine
    replay_engine: ReplayEngine
    allow_mock: bool = False

    @classmethod
    def create(
        cls,
        *,
        allow_mock: bool = False,
        store: CreativeStore | None = None,
        assets: AssetStore | None = None,
        provider_resolver: GenerationProviderResolver | None = None,
        worker_id: str | None = None,
        production: bool = False,
    ) -> "CreativeRuntime":
        if production and allow_mock:
            raise ValueError("production runtime cannot enable mock providers")
        assets = assets or (store.assets if store is not None else AssetStore())
        if store is None:
            store = CreativeStore.production(assets=assets) if production else CreativeStore(assets=assets)
        resolver = provider_resolver or GenerationProviderResolver(allow_mock=allow_mock)
        judge_registry = JudgeRegistry(allow_mock=allow_mock)
        engine = CreativeWorkflowEngine(
            store=store,
            resolver=resolver,
            allow_mock=allow_mock,
            worker_id=worker_id,
            judge_resolver=judge_registry.resolver,
        )
        load_templates()
        load_from_store(store)
        return cls(
            store=store,
            assets=store.assets,
            workflow_registry=resolve_workflow,
            workflow_resolver=WorkflowResolver(store=store),
            provider_resolver=resolver,
            engine=engine,
            judge_registry=judge_registry,
            cost_engine=CostEngine(store),
            replay_engine=ReplayEngine(engine),
            allow_mock=allow_mock,
        )

    @classmethod
    def production(cls, **kwargs: Any) -> "CreativeRuntime":
        kwargs.pop("allow_mock", None)
        return cls.create(production=True, allow_mock=False, **kwargs)

    @classmethod
    def testing(cls, **kwargs: Any) -> "CreativeRuntime":
        from creative.store import CreativeStore, sqlite_engine
        kwargs.setdefault("allow_mock", True)
        if kwargs.get("store") is None:
            assets = kwargs.get("assets")
            kwargs["store"] = CreativeStore(assets=assets, engine=sqlite_engine())
        return cls.create(production=False, **kwargs)

    def workflows(self):
        return list_workflows()


_RUNTIME: CreativeRuntime | None = None


def get_runtime(*, allow_mock: bool = False, production: bool | None = None, reset: bool = False, **kwargs: Any) -> CreativeRuntime:
    global _RUNTIME
    if reset:
        _RUNTIME = None
    if _RUNTIME is not None and not kwargs:
        if allow_mock and not _RUNTIME.allow_mock:
            _RUNTIME = None
        else:
            return _RUNTIME
    use_production = bool(production) if production is not None else not allow_mock
    runtime = CreativeRuntime.create(allow_mock=allow_mock, production=use_production, **kwargs)
    if not kwargs:
        _RUNTIME = runtime
    return runtime
