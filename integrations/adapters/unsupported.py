"""Explicitly disabled adapter for providers without a verified connector."""

from __future__ import annotations

from integrations.contracts.distribution import (
    DistributionJob,
    Integration,
    IntegrationCapabilities,
    MediaUploadResult,
    ProviderHealth,
    UnsupportedCapabilityError,
)


class UnsupportedDistributionAdapter:
    def __init__(self, integration: Integration) -> None:
        self.integration = integration

    def authenticate(self) -> bool:
        return False

    def health(self) -> ProviderHealth:
        return ProviderHealth(provider=self.integration.provider, reachable=False, authenticated=False, last_error="unsupported")

    def list_integrations(self) -> list[Integration]:
        return [self.integration]

    def get_integration(self, integration_id: str) -> Integration:
        if integration_id != self.integration.id:
            raise KeyError(integration_id)
        return self.integration

    def get_capabilities(self, integration_id: str) -> IntegrationCapabilities:
        return self.get_integration(integration_id).capabilities

    def get_settings(self, integration_id: str) -> dict:
        return {}

    def _unsupported(self, operation: str) -> None:
        raise UnsupportedCapabilityError(f"{self.integration.provider}: {operation} is unsupported")

    def validate_payload(self, job: DistributionJob) -> list[str]:
        return [f"{self.integration.provider}: connector is not verified"]

    def prepare_publish(self, job: DistributionJob) -> dict:
        return {"status": "unsupported", "provider": self.integration.provider}

    def upload_media(self, source_path: str) -> MediaUploadResult:
        self._unsupported("upload_media")
        raise UnsupportedCapabilityError("upload_media")

    def publish(self, job: DistributionJob) -> dict:
        self._unsupported("publish")
        raise UnsupportedCapabilityError("publish")

    def schedule(self, job: DistributionJob) -> dict:
        self._unsupported("schedule")
        raise UnsupportedCapabilityError("schedule")

    def get_status(self, provider_post_id: str) -> dict:
        self._unsupported("get_status")
        raise UnsupportedCapabilityError("get_status")

    def cancel(self, provider_post_id: str) -> dict:
        self._unsupported("cancel")
        raise UnsupportedCapabilityError("cancel")

    def get_analytics(self, provider_post_id: str) -> dict:
        self._unsupported("get_analytics")
        raise UnsupportedCapabilityError("get_analytics")

    def delete(self, provider_post_id: str) -> dict:
        return self.cancel(provider_post_id)
