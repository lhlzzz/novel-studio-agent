import pytest

from agents.distribution_agent import DistributionAgent
from content.models import ContentPackage
from integrations.contracts.distribution import Integration


def test_distribution_agent_fails_closed_without_verified_provider():
    agent = DistributionAgent()
    with pytest.raises(RuntimeError, match="not runtime verified"):
        agent.create_job(
            ContentPackage("pkg-1", "Test", "Hello"),
            platform="x",
            job_id="job-1",
        )


def test_distribution_agent_requires_active_account_mapping(tmp_path):
    accounts = tmp_path / "integrations.yaml"
    accounts.write_text(
        "provider: postiz\naccounts:\n  - platform: x\n    integration_id: x-1\n    status: pending\n",
        encoding="utf-8",
    )
    registry = {
        "postiz": Integration(
            "postiz", "postiz", "", "global", {}, "postiz", "postiz", True
        )
    }
    with pytest.raises(RuntimeError, match="no active verified"):
        DistributionAgent(registry=registry, accounts_path=accounts).create_job(
            ContentPackage("pkg-1", "Test", "Hello"),
            platform="x",
            job_id="job-1",
        )


def test_distribution_agent_syncs_normalized_analytics(monkeypatch):
    from integrations.contracts.distribution import IntegrationCapabilities

    class FakeAdapter:
        def get_analytics(self, post_id):
            assert post_id == "post-1"
            return {"views": 12, "likes": 3}

    captured = {}

    def fake_persist(metrics):
        captured["metrics"] = metrics

    monkeypatch.setattr("agents.distribution_agent.persist_metrics", fake_persist)
    agent = DistributionAgent(
        adapter=FakeAdapter(),
        registry={"postiz": Integration("postiz", "postiz", "", "global", IntegrationCapabilities(), "postiz", "postiz", True)},
    )

    result = agent.sync_analytics(
        publication_id="job-1",
        post_id="post-1",
        platform="x",
    )

    assert result.values["platform"] == "x"
    assert result.values["post_id"] == "post-1"
    assert result.values["views"] == 12
    assert captured["metrics"] == result
