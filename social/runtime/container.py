"""Unique social composition root. Production never defaults to InMemoryStore."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from integrations.persistence import DatabaseStore, InMemoryStore, JobStore
from social.accounts.manager import SocialAccountManager
from social.auth.oauth import OAuthStateStore
from social.auth.secrets import RuntimeSecretStore, production_secret_store
from social.reconciliation.service import SocialReconciliationService
from social.schedule.scheduler import MeitiScheduler


@dataclass
class SocialRuntime:
    store: JobStore
    secrets: RuntimeSecretStore
    manager: SocialAccountManager
    scheduler: MeitiScheduler
    oauth_states: OAuthStateStore
    production: bool = False

    @classmethod
    def create(
        cls,
        *,
        store: JobStore,
        secrets: RuntimeSecretStore,
        production: bool = False,
        adapter: Any | None = None,
    ) -> "SocialRuntime":
        if production and isinstance(store, InMemoryStore):
            raise ValueError("production social runtime cannot use InMemoryStore")
        manager = SocialAccountManager(store, secrets=secrets)
        scheduler = MeitiScheduler(store=store, manager=manager, adapter=adapter)
        return cls(
            store=store,
            secrets=secrets,
            manager=manager,
            scheduler=scheduler,
            oauth_states=OAuthStateStore(secrets),
            production=production,
        )

    @classmethod
    def production(cls, **kwargs: Any) -> "SocialRuntime":
        store = kwargs.pop("store", None) or DatabaseStore()
        secrets = kwargs.pop("secrets", None) or production_secret_store()
        return cls.create(store=store, secrets=secrets, production=True, **kwargs)

    @classmethod
    def testing(cls, **kwargs: Any) -> "SocialRuntime":
        from pathlib import Path
        import tempfile

        store = kwargs.pop("store", None) or InMemoryStore()
        secrets = kwargs.pop("secrets", None)
        if secrets is None:
            secrets = RuntimeSecretStore(Path(tempfile.mkdtemp(prefix="meiti-test-secrets-")))
        return cls.create(store=store, secrets=secrets, production=False, **kwargs)

    def agent(self, *, adapter: Any | None = None, provider_name: str | None = None):
        from agents.distribution_agent import DistributionAgent

        return DistributionAgent(
            store=self.store,
            manager=self.manager,
            adapter=adapter,
            provider_name=provider_name,
            secrets=self.secrets,
        )

    def reconciliation(self, adapter: Any) -> SocialReconciliationService:
        return SocialReconciliationService(adapter, store=self.store)
