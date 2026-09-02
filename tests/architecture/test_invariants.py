from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_workspaces():
    assert not (ROOT / "workspaces").exists()
    assert not (ROOT / "workspace").exists()
    assert not (ROOT / "platform-workspaces").exists()


def test_no_platform_agents():
    forbidden = tuple(
        prefix + suffix
        for prefix in ("xiaohongshu", "douyin", "tiktok", "instagram", "platform")
        for suffix in ("_agent", "-agent", "_agents")
    )
    for path in (ROOT / "agents").rglob("*"):
        name = path.name.lower()
        assert all(token not in name for token in forbidden)


def test_distribution_single_owner():
    owners = list((ROOT / "agents").glob("*distribution*"))
    assert (ROOT / "agents/distribution_agent.py").exists()
    assert (ROOT / "agents/distribution/runtime.py").read_text(encoding="utf-8").count("from agents.distribution_agent import DistributionAgent") == 1
    assert len(owners) >= 2


def test_distribution_uses_social_provider_resolver():
    source = (ROOT / "agents/distribution_agent.py").read_text(encoding="utf-8")
    assert "resolve_adapter" in source
    assert "resolve_social_provider" in source


def test_no_direct_native_adapter_import_from_distribution_agent():
    source = (ROOT / "agents/distribution_agent.py").read_text(encoding="utf-8")
    assert "XAdapter" not in source
    service = (ROOT / "integrations/distribution_service.py").read_text(encoding="utf-8")
    assert ("providers." + "pos" + "tiz") not in service
    assert "social.providers.x" not in service


def test_capabilities_require_verification():
    from governance.distribution_gate import check_distribution_job
    from integrations.contracts.distribution import ContentVariant, DistributionJob
    from social.accounts.models import SocialAccount, SocialProviderCapabilities, enable_account
    account = enable_account(SocialAccount("i", "x", "x", status="VERIFIED", capabilities=SocialProviderCapabilities(publish=True, text=True)))
    job = DistributionJob("j", "p", "i", ContentVariant("i", "test"))
    failures = check_distribution_job(
        job, account, content_valid=True, evidence_valid=True, account_valid=True,
        media_valid=True, approval_valid=True, provider_verified=True, integration_verified=True,
        capability_verified=False, idempotency_valid=True, media_uploaded=True, payload_valid=True,
    )
    assert "capability unverified" in failures


def test_external_actions_require_gate():
    from integrations.distribution_service import DistributionService, ExternalActionBlocked
    from tests.fixtures.fakes import FakeAdapter, job
    import pytest

    adapter = FakeAdapter()
    with pytest.raises(ExternalActionBlocked):
        DistributionService(adapter).execute(job(), gate_check=lambda item: False)
    assert adapter.published is False


def test_media_upload_before_publish(tmp_path):
    from integrations.contracts.distribution import ContentVariant, DistributionJob
    from tests.fixtures.fakes import FakeAdapter

    media = tmp_path / "pic.png"
    media.write_bytes(b"png-bytes")
    adapter = FakeAdapter()
    item = DistributionJob("job-1", "pkg-1", "i", ContentVariant("i", "hello", media=(str(media),)))
    _, uploaded = adapter.ensure_media(item)
    assert uploaded[0].remote_path
    assert uploaded[0].source_hash
    assert uploaded[0].remote_id != str(media)


def test_publication_persisted():
    from integrations.distribution_service import DistributionService
    from integrations.persistence import InMemoryStore
    from tests.fixtures.fakes import FakeAdapter, job

    store = InMemoryStore()
    publication = DistributionService(FakeAdapter(), store=store).execute(job(), gate_check=lambda item: True)
    saved = store.get_publication("job-1")
    assert saved is not None
    assert saved.distribution_job_id == publication.distribution_job_id == "job-1"


def test_ids_are_separated():
    from integrations.distribution_service import DistributionService
    from integrations.persistence import InMemoryStore
    from tests.fixtures.fakes import FakeAdapter, job

    saved = DistributionService(FakeAdapter(), store=InMemoryStore()).execute(job(), gate_check=lambda item: True)
    assert saved.distribution_job_id != saved.provider_post_id
    assert saved.provider_post_id != saved.platform_object_id
    assert saved.distribution_job_id != saved.platform_object_id


def test_idempotent_publish():
    from integrations.distribution_service import DistributionService
    from integrations.persistence import InMemoryStore
    from tests.fixtures.fakes import FakeAdapter, job

    adapter = FakeAdapter()
    store = InMemoryStore()
    service = DistributionService(adapter, store=store)
    first = service.execute(job(), gate_check=lambda item: True)
    adapter.published = False
    second = service.execute(job(), gate_check=lambda item: True)
    assert first.provider_post_id == second.provider_post_id
    assert adapter.published is False


def test_v43_doctor_keeps_unverified_live_paths_blocked():
    from scripts.meiti_doctor import check_lechuang_contract, check_real_creative_e2e, check_real_distribution_e2e
    assert check_lechuang_contract()["status"] == "BLOCKED"
    assert check_real_creative_e2e()["status"] == "BLOCKED"
    assert check_real_distribution_e2e()["status"] == "BLOCKED"


def test_retry_policy():
    from social.providers.errors import RateLimitError, ServerError, ValidationError, classify_http_error

    assert classify_http_error(503, "bad").retryable is True
    assert isinstance(classify_http_error(429, "slow", retry_after=2), RateLimitError)
    assert ValidationError("bad").retryable is False
    assert ServerError("down").retryable is True


def test_dead_letter():
    from services.queue import WorkQueue

    queue = WorkQueue(max_attempts=3)
    queue.enqueue("job-1", {"action": "publish"})
    item = None
    for _ in range(3):
        item = queue.fail("job-1", error_code="ValidationError", error_message="bad payload")
    assert item.status == "dead_letter"
    assert item.attempt_count == 3
    assert item.error_code == "ValidationError"


def test_no_secret_logging():
    from governance.observability import log_event, redact

    payload = redact({"api_key": "secret-value", "X_CLIENT_SECRET": "abc", "message": "Authorization: Bearer xyz"})
    text = str(payload)
    assert "secret-value" not in text
    assert "Bearer xyz" not in text
    logged = log_event(agent="distribution-agent", action="publish", status="ok", api_key="should-not-leak")
    assert logged["api_key"] == "[redacted]"
    source = (ROOT / "social/providers/http.py").read_text(encoding="utf-8")
    assert "print(self" not in source
    obs = (ROOT / "governance/observability.py").read_text(encoding="utf-8")
    assert "access_token" in obs
    assert "authorization" in obs
