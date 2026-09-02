"""Meiti social and distribution API. Agents select accounts; adapters execute."""

from __future__ import annotations

from typing import Any

from social.runtime.container import SocialRuntime


class SocialAccountAPI:
    def __init__(self, manager=None, *, runtime: SocialRuntime | None = None) -> None:
        if manager is None and runtime is None:
            raise ValueError("SocialAccountAPI requires SocialRuntime")
        self.manager = manager or runtime.manager

    def list_accounts(self):
        return self.manager.list_accounts()

    def get_account(self, account_id: str):
        return self.manager.get_account(account_id)

    def connect_account(self, provider: str, **authorization: Any):
        return self.manager.connect_account(provider, authorization=authorization or None)

    def disconnect_account(self, account_id: str):
        return self.manager.disconnect_account(account_id)

    def refresh_account(self, account_id: str):
        return self.manager.refresh_account(account_id)

    def verify_account(self, account_id: str):
        return self.manager.verify_account(account_id)


class DistributionAPI:
    def __init__(self, agent: Any | None = None, *, runtime: SocialRuntime | None = None) -> None:
        self.agent = agent
        self.runtime = runtime

    def _agent(self):
        if self.agent is None:
            runtime = self.runtime
            if runtime is None:
                raise ValueError("DistributionAPI requires SocialRuntime")
            self.agent = runtime.agent()
        return self.agent

    def publish(self, job):
        return self._agent().execute(job)

    def schedule(self, job):
        return self._agent().schedule(job)

    def cancel(self, job_id: str):
        return self._agent().cancel(job_id)

    def status(self, job_id: str):
        return self._agent().status(job_id)

    def reconcile(self, job_id: str):
        return self._agent().reconcile(job_id)

    def analytics(self, *, publication_id: str, post_id: str, platform: str):
        return self._agent().sync_analytics(publication_id=publication_id, post_id=post_id, platform=platform)
