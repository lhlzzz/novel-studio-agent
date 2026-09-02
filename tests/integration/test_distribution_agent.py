import pytest

from content.models import ContentPackage
from social.runtime.container import SocialRuntime


def test_distribution_agent_fails_closed_without_verified_provider():
    agent = SocialRuntime.testing().agent()
    with pytest.raises(RuntimeError, match="not runtime verified"):
        agent.create_job(
            ContentPackage("pkg-1", "Test", "Hello"),
            platform="x",
            job_id="job-1",
        )


def test_distribution_agent_requires_verified_account():
    agent = SocialRuntime.testing().agent()
    with pytest.raises(RuntimeError, match="no active verified"):
        agent.create_job(
            ContentPackage("pkg-1", "Test", "Hello"),
            platform="x",
            job_id="job-1",
        )


def test_distribution_agent_syncs_normalized_analytics(monkeypatch):
    class FakeAdapter:
        def get_analytics(self, post_id):
            assert post_id == "post-1"
            return {"views": 12, "likes": 3, "comments": None, "shares": None, "followers_delta": None}

        def analytics(self, publication):
            return self.get_analytics(publication.provider_post_id)

    captured = {}

    def fake_persist(metrics):
        captured["metrics"] = metrics

    monkeypatch.setattr("agents.distribution_agent.persist_metrics", fake_persist)
    agent = SocialRuntime.testing().agent(adapter=FakeAdapter())

    result = agent.sync_analytics(
        publication_id="job-1",
        post_id="post-1",
        platform="x",
    )

    assert result.values["platform"] == "x"
    assert result.values["post_id"] == "post-1"
    assert result.values["views"] == 12
    assert captured["metrics"] == result
