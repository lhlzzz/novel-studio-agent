from uuid import uuid4

import pytest

from agents.distribution_agent import DistributionAgent
from content.assets import PlatformAssetService
from content.models import (
    AnalyticsRecord,
    CalendarSlotConflict,
    ConfigurationBlocked,
    ContentPackage,
    CreativeContext,
    IsolationError,
    LearningRecord,
    PlatformAccount,
)
from content.planner import EpisodePlanner
from content.runtime import ContinuityRuntime
from integrations.contracts.distribution import ContentVariant, DistributionJob
from tests.unit.test_account_continuity import _seed_account
from tests.unit.test_platform_asset_dna import _png


@pytest.fixture
def runtime():
    return ContinuityRuntime.testing()


def _account(runtime):
    return _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")


def _compile(runtime, account, title="健身日常"):
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title=title, brief=title)
    prompt = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request=title, kind="IMAGE", episode=episode)
    return episode, prompt


def test_prevalidation_failure_writes_no_production_rows(runtime, tmp_path):
    account = _account(runtime)
    episode, prompt = _compile(runtime, account)
    with pytest.raises(FileNotFoundError):
        PlatformAssetService(runtime.store).import_asset(
            tmp_path / "missing.png",
            account_id=account.account_id,
            platform="xiaohongshu",
            episode_id=episode.episode_id,
            asset_role="GENERATED_PRIMARY",
            prompt_id=prompt.prompt_id,
            root=tmp_path / "assets",
        )
    kinds = {item.kind for item in runtime.store.list_evidence(account_id=account.account_id, episode_id=episode.episode_id)}
    assert not any(kind.endswith("REAL_ASSET_IMPORTED") for kind in kinds)
    assert runtime.store.get_receipt_for_asset("missing") is None
    stored = runtime.store.get_episode(episode.episode_id, account_id=account.account_id)
    assert stored.primary_asset_id is None


def test_qa_failure_does_not_create_successful_asset(runtime, tmp_path, monkeypatch):
    account = _account(runtime)
    episode, prompt = _compile(runtime, account)
    path = _png(tmp_path, "bad.png", 3)
    monkeypatch.setattr(
        "creative.judges.technical.TechnicalQA.inspect_image",
        lambda self, asset: {"decision": "fail", "failures": ["resolution"]},
    )
    with pytest.raises(ConfigurationBlocked) as exc:
        PlatformAssetService(runtime.store).import_asset(
            path,
            account_id=account.account_id,
            platform="xiaohongshu",
            episode_id=episode.episode_id,
            asset_role="GENERATED_PRIMARY",
            prompt_id=prompt.prompt_id,
            root=tmp_path / "assets",
        )
    assert exc.value.code == "QA_FAILED"
    stored = runtime.store.get_episode(episode.episode_id, account_id=account.account_id)
    assert stored.primary_asset_id is None
    kinds = {item.kind for item in runtime.store.list_evidence(account_id=account.account_id)}
    assert "QA_FAILED" in kinds
    assert not any(kind.endswith("REAL_ASSET_IMPORTED") for kind in kinds)


def test_lineage_failure_rolls_back_import(runtime, tmp_path, monkeypatch):
    account = _account(runtime)
    episode, prompt = _compile(runtime, account)
    original = runtime.store.allocate_attempt

    def boom(*args, **kwargs):
        raise RuntimeError("lineage boom")

    monkeypatch.setattr(runtime.store, "allocate_attempt", boom)
    with pytest.raises(RuntimeError, match="lineage boom"):
        PlatformAssetService(runtime.store).import_asset(
            _png(tmp_path, "a.png", 11),
            account_id=account.account_id,
            platform="xiaohongshu",
            episode_id=episode.episode_id,
            asset_role="GENERATED_PRIMARY",
            prompt_id=prompt.prompt_id,
            root=tmp_path / "assets",
        )
    stored = runtime.store.get_episode(episode.episode_id, account_id=account.account_id)
    assert stored.primary_asset_id is None
    kinds = {item.kind for item in runtime.store.list_evidence(account_id=account.account_id, episode_id=episode.episode_id)}
    assert not any(kind.endswith("REAL_ASSET_IMPORTED") for kind in kinds)
    monkeypatch.setattr(runtime.store, "allocate_attempt", original)


def test_receipt_failure_rolls_back_import(runtime, tmp_path, monkeypatch):
    account = _account(runtime)
    episode, prompt = _compile(runtime, account)

    def boom(*args, **kwargs):
        raise RuntimeError("receipt boom")

    monkeypatch.setattr(runtime.store, "save_receipt", boom)
    with pytest.raises(RuntimeError, match="receipt boom"):
        PlatformAssetService(runtime.store).import_asset(
            _png(tmp_path, "a.png", 12),
            account_id=account.account_id,
            platform="xiaohongshu",
            episode_id=episode.episode_id,
            asset_role="GENERATED_PRIMARY",
            prompt_id=prompt.prompt_id,
            root=tmp_path / "assets",
        )
    stored = runtime.store.get_episode(episode.episode_id, account_id=account.account_id)
    assert stored.primary_asset_id is None
    kinds = {item.kind for item in runtime.store.list_evidence(account_id=account.account_id, episode_id=episode.episode_id)}
    assert not any(kind.endswith("REAL_ASSET_IMPORTED") for kind in kinds)


def test_episode_without_prompt_does_not_use_latest(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    first = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="has prompt", brief="has prompt")
    runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="has prompt", kind="IMAGE", episode=first)
    second = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="no prompt", brief="no prompt")
    payload = runtime.production_readiness(account_id=account.account_id, episode_id=second.episode_id, persist=False)
    assert payload["checks"]["PROMPT"] == "FAIL"
    assert payload["CORE_PRODUCTION"] != "READY"


def test_stale_character_world_series_fail(runtime):
    account = _account(runtime)
    original = account
    runtime.store.save_account(PlatformAccount(**{**original.__dict__, "character_id": "missing-character"}))
    payload = runtime.production_readiness(account_id=original.account_id, persist=False)
    assert payload["detail"]["error_codes"]["character"] == "CHARACTER_NOT_FOUND"
    assert payload["ACCOUNT_CONFIGURATION"] == "FAIL"
    runtime.store.save_account(PlatformAccount(**{**original.__dict__, "world_id": "missing-world"}))
    payload = runtime.production_readiness(account_id=original.account_id, persist=False)
    assert payload["detail"]["error_codes"]["world"] == "WORLD_NOT_FOUND"
    runtime.store.save_account(PlatformAccount(**{**original.__dict__, "series_id": "missing-series"}))
    payload = runtime.production_readiness(account_id=original.account_id, persist=False)
    assert payload["detail"]["error_codes"]["series"] == "SERIES_NOT_FOUND"


def test_missing_package_fails(runtime):
    account = _account(runtime)
    episode, _prompt = _compile(runtime, account)
    payload = runtime.production_readiness(account_id=account.account_id, episode_id=episode.episode_id, persist=False)
    assert payload["checks"]["PACKAGE"] == "PACKAGE_MISSING"
    assert payload["CORE_PRODUCTION"] != "READY"


def test_draft_and_paused_accounts_are_not_production_ready(runtime):
    account = _account(runtime)
    runtime.store.save_account(PlatformAccount(**{**account.__dict__, "status": "DRAFT"}))
    payload = runtime.production_readiness(account_id=account.account_id, persist=False)
    assert payload["ACCOUNT_CONFIGURATION"] == "FAIL"
    assert payload["CORE_PRODUCTION"] != "READY"
    runtime.store.save_account(PlatformAccount(**{**account.__dict__, "status": "PAUSED"}))
    payload = runtime.production_readiness(account_id=account.account_id, persist=False)
    assert payload["ACCOUNT_CONFIGURATION"] == "FAIL"
    runtime.store.save_account(PlatformAccount(**{**account.__dict__, "status": "ACTIVE"}))
    payload = runtime.production_readiness(account_id=account.account_id, persist=False)
    assert payload["ACCOUNT_CONFIGURATION"] == "PASS"


def test_unverified_learning_does_not_update_profile_or_prompt(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="learn", brief="learn")
    profile_before = runtime.store.get_learning_profile(account.account_id, "xiaohongshu")
    runtime.record_learning(LearningRecord(
        learning_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        what_worked="should not leak",
        next_recommendation="do not use this",
        evidence_status="NOT_VERIFIED",
    ))
    profile_after = runtime.store.get_learning_profile(account.account_id, "xiaohongshu")
    assert profile_after.successful_patterns == profile_before.successful_patterns
    assert profile_after.prompt_patterns == profile_before.prompt_patterns
    prompt = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="new scene", kind="IMAGE", episode=episode)
    assert all("do not use this" not in item for item in prompt.learning_basis)


def test_manual_analytics_cannot_verify_learning(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="a", brief="a")
    analytics = runtime.record_analytics(AnalyticsRecord(
        analytics_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        likes=12,
        publication_id="looks-real",
        origin="MANUAL",
    ))
    assert analytics.origin == "MANUAL"
    assert analytics.verification_status == "UNVERIFIED"
    kinds = {item.kind for item in runtime.store.list_evidence(account_id=account.account_id)}
    assert "MANUAL_ANALYTICS_OBSERVATION" in kinds
    assert "ANALYTICS_IMPORTED" not in kinds
    learning = runtime.record_learning(LearningRecord(
        learning_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        analytics_id=analytics.analytics_id,
        what_worked="manual",
        evidence_status="VERIFIED",
    ))
    assert learning.evidence_status == "NOT_ENOUGH_EVIDENCE"
    run = runtime.store.get_production_run(runtime.store.get_episode(episode.episode_id, account_id=account.account_id).production_run_id) if runtime.store.get_episode(episode.episode_id, account_id=account.account_id).production_run_id else None
    if run is not None:
        assert run.learning_id is None
        assert run.status != "LEARNING_VERIFIED"


def test_provider_analytics_can_verify_learning(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="p", brief="p")
    runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="p", kind="IMAGE", episode=episode)
    analytics = runtime.record_analytics(AnalyticsRecord(
        analytics_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        likes=40,
        publication_id="pub-1",
        origin="PROVIDER",
        verification_status="VERIFIED",
        provider="xiaohongshu",
        provider_payload={"observed_at": "now", "likes": 40},
    ))
    assert analytics.origin == "PROVIDER"
    assert analytics.verification_status == "VERIFIED"
    learning = runtime.record_learning(LearningRecord(
        learning_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        analytics_id=analytics.analytics_id,
        what_worked="verified light",
        next_recommendation="keep verified light",
        evidence_status="VERIFIED",
    ))
    assert learning.evidence_status == "VERIFIED"
    profile = runtime.store.get_learning_profile(account.account_id, "xiaohongshu")
    assert "verified light" in profile.successful_patterns
    prompt = runtime.compile_prompt(
        account_id=account.account_id,
        platform="xiaohongshu",
        request="next verified",
        kind="IMAGE",
        episode=runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="next", brief="next"),
    )
    assert any("verified light" in item or "keep verified" in item for item in prompt.learning_basis)


def test_handoff_does_not_set_last_published_episode(runtime, tmp_path):
    account = _account(runtime)
    episode, prompt = _compile(runtime, account)
    imported = runtime.import_asset(
        _png(tmp_path, "h.png", 8),
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        asset_role="GENERATED_PRIMARY",
        prompt_id=prompt.prompt_id,
        root=tmp_path / "assets",
    )
    context = CreativeContext(
        context_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        character_id=account.character_id,
        world_id=account.world_id,
        series_id=episode.series_id,
        episode_id=episode.episode_id,
        user_request="h",
        creative_request="h",
        normalized_prompt="h",
    )
    package = runtime.package_from_generation(context=context, assets=[imported["asset"]], title="h", prompt_id=prompt.prompt_id)
    runtime.record_handoff(package=package, handoff=type("H", (), {"handoff_id": "hx", "status": "READY_FOR_XHS"})())
    state = runtime.store.get_operating_state(account.account_id)
    assert state.last_published_episode != episode.episode_id
    run = runtime.store.get_production_run(runtime.store.get_episode(episode.episode_id, account_id=account.account_id).production_run_id)
    assert run.status == "HANDED_OFF"
    assert run.handoff_id == "hx"
    stored = runtime.store.get_episode(episode.episode_id, account_id=account.account_id)
    assert stored.content_status == "HANDOFF_READY"
    assert stored.content_status != "PUBLISHED"


def test_calendar_slot_conflict(runtime):
    account = _account(runtime)
    planner = EpisodePlanner(runtime.store)
    first = planner.ensure_calendar(account_id=account.account_id, date="2026-09-05", topic="a", episode_id="ep-1", slot="noon")
    assert first.episode_id == "ep-1"
    with pytest.raises(CalendarSlotConflict):
        planner.ensure_calendar(account_id=account.account_id, date="2026-09-05", topic="b", episode_id="ep-2", slot="noon")


def test_gate_blocks_media_not_uploaded():
    from social.publish.gate import admit
    from tests.fakes.social.adapter import FakeAdapter

    adapter = FakeAdapter()
    job = DistributionJob(
        "j",
        "p",
        "i",
        ContentVariant("i", "hello", media=("a.jpg",), metadata={"approval": "approved"}),
        idempotency_key="k",
        provider="x",
        platform="x",
    )
    decision = admit(job, adapter=adapter, account=adapter.account)
    assert decision.ready is False
    assert "MEDIA_NOT_UPLOADED" in decision.reasons


def test_distribution_blocks_package_account_mismatch():
    from social.accounts.models import SocialAccount, SocialProviderCapabilities
    from social.runtime.container import SocialRuntime

    runtime = SocialRuntime.testing()
    caps = SocialProviderCapabilities.from_claimed({"publish": True}, verified=True)
    a = SocialAccount("acc-a", "x", "x", username="a", status="ENABLED", capabilities=caps, provider_account_id="a")
    b = SocialAccount("acc-b", "x", "x", username="b", status="ENABLED", capabilities=caps, provider_account_id="b")
    runtime.store.save_account(a)
    runtime.store.save_account(b)
    agent = runtime.agent(adapter=type("Adapter", (), {
        "authenticate": lambda self=None: True,
        "list_accounts": lambda: [a],
        "verify_capabilities": lambda account_id: caps,
        "secrets": None,
    })())
    package = ContentPackage("pkg-1", "Test", "Hello", account_id="acc-b", platform="x", episode_id="ep-1")
    with pytest.raises(IsolationError) as exc:
        agent.create_job(package, platform="x", job_id="job-1", account_id="acc-a")
    assert exc.value.code == "PACKAGE_ACCOUNT_MISMATCH"


def test_cross_platform_primary_cannot_become_compiler_primary(runtime, tmp_path):
    xhs = _account(runtime)
    dy = _seed_account(runtime, platform="douyin", name="B", character="训练角色", world="训练世界", series="训练系列")
    xhs_ep = runtime.continue_series(account_id=xhs.account_id, series_id=runtime.store.active_series(xhs.account_id).series_id, title="X1", brief="x")
    dy_ep = runtime.continue_series(account_id=dy.account_id, series_id=runtime.store.active_series(dy.account_id).series_id, title="D1", brief="d")
    xhs_asset = PlatformAssetService(runtime.store).import_asset(
        _png(tmp_path, "xhs.png", 33),
        account_id=xhs.account_id,
        platform="xiaohongshu",
        episode_id=xhs_ep.episode_id,
        asset_role="GENERATED_PRIMARY",
        no_prompt_reference=True,
        root=tmp_path / "assets",
    )["asset"]
    prompt = runtime.compile_prompt(
        account_id=dy.account_id,
        platform="douyin",
        request="new dy",
        kind="IMAGE",
        episode=dy_ep,
        reference_assets=[xhs_asset],
    )
    assert xhs_asset.asset_id in prompt.reference_assets
    assert xhs_asset.asset_id not in prompt.source_assets
