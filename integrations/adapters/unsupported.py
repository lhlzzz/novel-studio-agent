"""Explicitly disabled adapter for providers without a verified connector."""

from __future__ import annotations

from integrations.contracts.distribution import (
    DistributionJob,
    Integration,
    IntegrationCapabilities,
    UnsupportedCapabilityError,
)


class UnsupportedDistributionAdapter:
    def __init__(self, integration: Integration) -> None:
        self.integration = integration

    def list_integrations(self) -> list[Integration]:
        return [self.integration]

    def get_integration(self, integration_id: str) -> Integration:
        if integration_id != self.integration.id:
            raise KeyError(integration_id)
        return self.integration

    def get_capabilities(self, integration_id: str) -> IntegrationCapabilities:
        return self.get_integration(integration_id).capabilities

    def _unsupported(self, operation: str) -> None:
        raise UnsupportedCapabilityError(f"{self.integration.provider}: {operation} is unsupported")

    def validate_payload(self, job: DistributionJob) -> list[str]:
        return [f"{self.integration.provider}: connector is not verified"]

    def prepare_publish(self, job: DistributionJob) -> dict:
        return {"status": "unsupported", "provider": self.integration.provider}

    def publish(self, job: DistributionJob) -> dict:
        self._unsupported("publish")

    schedule = publish
    get_status = publish
    delete = publish
    get_analytics = publish
