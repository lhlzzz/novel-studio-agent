import pytest

from integrations.contracts.distribution import ContentVariant, DistributionJob, Integration, IntegrationCapabilities
from integrations.distribution_service import DistributionService, ExternalActionBlocked


class FakeAdapter:
    def __init__(self):
        self.integration = Integration("i", "x", "account", "global",
                                       IntegrationCapabilities(publish=True), "postiz", "postiz", True)
        self.published = False

    def get_integration(self, integration_id):
        return self.integration

    def get_settings(self, integration_id):
        return {"rules": []}

    def validate_payload(self, job):
        return []

    def publish(self, job):
        self.published = True
        return {
            "id": "postiz-post-1",
            "externalId": "x-status-1",
            "status": "queued",
        }

    def schedule(self, job):
        return self.publish(job)


def _job():
    return DistributionJob("job-1", "test-package-001", "i", ContentVariant("i", "test"))


def test_service_dry_run_reads_settings_without_external_publish():
    adapter = FakeAdapter()
    result = DistributionService(adapter).dry_run(_job())
    assert result["status"] == "READY"
    assert adapter.published is False


def test_service_requires_gate_before_external_publish():
    adapter = FakeAdapter()
    service = DistributionService(adapter)
    with pytest.raises(ExternalActionBlocked):
        service.execute(_job(), gate_check=lambda job: False)
    assert adapter.published is False


def test_service_returns_external_id_after_gate_passes():
    adapter = FakeAdapter()
    publication = DistributionService(adapter).execute(_job(), gate_check=lambda job: True)
    assert publication.postiz_post_id == "postiz-post-1"
    assert publication.external_id == "x-status-1"
    assert adapter.published is True
