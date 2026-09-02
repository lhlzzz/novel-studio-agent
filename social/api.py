"""Meiti social and distribution API. Agents select accounts; adapters execute."""

from __future__ import annotations

from typing import Any

from social.accounts.manager import SocialAccountManager
from social.providers.resolver import resolve_social_provider


class SocialAccountAPI:
    def __init__(self, manager: SocialAccountManager | None = None) -> None:
        self.manager = manager or SocialAccountManager()

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
    def __init__(self, agent: Any | None = None) -> None:
        self.agent = agent

    def _agent(self):
        if self.agent is None:
            from agents.distribution_agent import DistributionAgent
            self.agent = DistributionAgent()
        return self.agent

    def publish(self, job, **gate: bool):
        return self._agent().execute(job, **gate)

    def schedule(self, job, **gate: bool):
        return self._agent().schedule(job, **gate)

    def cancel(self, job_id: str):
        return self._agent().cancel(job_id)

    def status(self, job_id: str):
        return self._agent().status(job_id)

    def reconcile(self, job_id: str):
        return self._agent().reconcile(job_id)

    def analytics(self, *, publication_id: str, post_id: str, platform: str):
        return self._agent().sync_analytics(publication_id=publication_id, post_id=post_id, platform=platform)
