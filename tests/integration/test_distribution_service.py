import pytest

from integrations.distribution_service import DistributionService, ExternalActionBlocked
from tests.fixtures.fakes import FakeAdapter, job as _job


def test_service_dry_run_reads_settings_without_external_publish():
    adapter = FakeAdapter()
    result = DistributionService(adapter, store=__import__("integrations.persistence", fromlist=["InMemoryStore"]).InMemoryStore()).dry_run(_job())
    assert result["status"] == "READY"
    assert adapter.published is False


def test_service_requires_gate_before_external_publish():
    adapter = FakeAdapter()
    service = DistributionService(adapter, store=__import__("integrations.persistence", fromlist=["InMemoryStore"]).InMemoryStore())
    with pytest.raises(ExternalActionBlocked):
        service.execute(_job(), gate_check=lambda job: False)
    assert adapter.published is False


def test_service_returns_external_id_after_gate_passes():
    adapter = FakeAdapter()
    publication = DistributionService(adapter, store=__import__("integrations.persistence", fromlist=["InMemoryStore"]).InMemoryStore()).execute(_job(), gate_check=lambda job: True)
    assert publication.provider_post_id == "x-post-1"
    assert publication.platform_object_id == "x-status-1"
    assert publication.account_id == "i"
    assert adapter.published is True
