from uuid import uuid4

import pytest

from content.assets import PlatformAssetService
from content.models import (
    AnalyticsRecord,
    ConfigurationBlocked,
    CreativeContext,
    IsolationError,
    LearningRecord,
)
from content.runtime import ContinuityRuntime
from tests.unit.test_account_continuity import _seed_account
from tests.unit.test_platform_asset_dna import _png


@pytest.fixture
def runtime():
    return ContinuityRuntime.testing()


def _account(runtime):
    return _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")


def test_account_profile_and_operating_state_are_separate(runtime):
    account = _account(runtime)
    profile = runtime.store.get_account_profile(account.account_id)
    state = runtime.store.get_operating_state(account.account_id)
    assert profile is not None
    assert state is not None
    assert profile.account_id == state.account_id
    assert "current_task" not in profile.__dict__ or not hasattr(profile, "current_task")
    assert state.current_task is None or isinstance(state.current_task, (str, type(None)))
    assert profile.account_objective.source in {"UNKNOWN", "DEFAULT", "USER_OVERRIDE", "USER_DEFINED"}


def test_manual_override_records_audit(runtime):
    account = _account(runtime)
    profile = runtime.override_profile(account.account_id, field_name="positioning", value="认真生活日记", reason="用户改定位", changed_by="operator")
    assert profile.positioning.source == "USER_OVERRIDE"
    assert profile.positioning.value == "认真生活日记"
    rows = runtime.store.list_overrides(account.account_id)
    assert rows and rows[0].reason == "用户改定位"
    assert rows[0].changed_by == "operator"


def test_character_override_creates_new_version_without_mutating_history(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    day1 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="v1", brief="第一版发型")
    prompt1 = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="第一版发型", kind="IMAGE", episode=day1)
    character = runtime.override_character(account.account_id, field_name="hair_profile", value={"style": "low bun"}, reason="改发型")
    assert character.version == 2
    day2 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="v2", brief="新发型")
    prompt2 = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="新发型新场景", kind="IMAGE", episode=day2, intent="CONTINUE")
    stored = runtime.store.get_episode(day1.episode_id, account_id=account.account_id)
    assert stored.character_revision == 1
    assert stored.prompt_id == prompt1.prompt_id
    latest = runtime.store.get_episode(day2.episode_id, account_id=account.account_id)
    assert latest.character_revision == 2
    revisions = runtime.store.list_character_revisions(character.character_id)
    assert [item.version for item in revisions] == [1, 2]


def test_compile_creates_production_task_chain(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="健身日常", brief="明天发一条小红书健身日常")
    runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="明天发一条小红书健身日常", kind="IMAGE", episode=episode)
    tasks = runtime.store.list_tasks(account_id=account.account_id, episode_id=episode.episode_id)
    types = [item.task_type for item in tasks]
    assert types == ["CONTENT_PLAN", "PROMPT_GENERATION", "CREATIVE_EXECUTION", "ASSET_IMPORT", "QA", "PACKAGE", "HANDOFF", "ANALYTICS", "LEARNING"]
    creative = next(item for item in tasks if item.task_type == "CREATIVE_EXECUTION")
    assert creative.status == "WAITING_OPERATOR"
    assert creative.next_task_type == "ASSET_IMPORT"


def test_next_action_is_operator_creative(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="健身", brief="健身")
    runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="健身日常", kind="IMAGE", episode=episode)
    nxt = runtime.get_next_action(account_id=account.account_id)
    assert nxt is not None
    assert nxt.task_type == "CREATIVE_EXECUTION"
    assert nxt.status == "WAITING_OPERATOR"


def test_today_and_blocked_tasks(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="今日", brief="今日")
    runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="今日内容", kind="IMAGE", episode=episode)
    today = runtime.get_today_tasks(account_id=account.account_id)
    assert today
    assert runtime.get_blocked_tasks(account_id=account.account_id) == []


def test_content_calendar_and_tomorrow(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="咖啡", brief="咖啡")
    runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="咖啡店日常", kind="IMAGE", episode=episode)
    rows = runtime.calendar(account_id=account.account_id)
    assert rows and rows[0]["status"] == "PRODUCING"
    tomorrow = runtime.tomorrow(account_id=account.account_id)
    assert tomorrow["platform"] == "xiaohongshu"
    assert tomorrow["creative_task"] == "CREATIVE_EXECUTION"
    assert tomorrow["topic"]


def test_episode_planner_is_not_random(runtime):
    account = _account(runtime)
    first = runtime.plan_next(account_id=account.account_id, request="晨跑")
    second = runtime.plan_next(account_id=account.account_id, request="晨跑")
    assert first.freshness == "NEW_PRIMARY_REQUIRED"
    assert first.topic == second.topic
    assert "platform=xiaohongshu" in first.reason


def test_topic_rotation_avoids_recent_same_topic(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="晨跑", brief="晨跑")
    runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="晨跑", brief="晨跑")
    concept = runtime.plan_next(account_id=account.account_id)
    assert concept.topic != "晨跑"


def test_prompt_is_copy_ready(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="健身", brief="健身")
    prompt = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="健身日常", kind="IMAGE", episode=episode)
    assert prompt.copy_ready
    assert "CHARACTER LOCK" in prompt.copy_ready or "character" in prompt.copy_ready.lower() or prompt.character_lock
    assert prompt.prompt_hash


def test_primary_import_requires_prompt_or_exception(runtime, tmp_path):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="导入", brief="导入")
    with pytest.raises(ConfigurationBlocked) as exc:
        PlatformAssetService(runtime.store).import_asset(
            _png(tmp_path, "a.png", 3),
            account_id=account.account_id,
            platform="xiaohongshu",
            episode_id=episode.episode_id,
            asset_role="GENERATED_PRIMARY",
            root=tmp_path / "assets",
        )
    assert exc.value.code == "NO_PROMPT_REFERENCE"


def test_human_chain_import_package_handoff(runtime, tmp_path):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="健身日常", brief="健身日常")
    prompt = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="健身日常", kind="IMAGE", episode=episode)
    imported = runtime.import_asset(
        _png(tmp_path, "day.png", 21),
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        asset_role="GENERATED_PRIMARY",
        prompt_id=prompt.prompt_id,
        root=tmp_path / "assets",
    )
    asset = imported["asset"]
    context = CreativeContext(
        context_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        character_id=account.character_id,
        world_id=account.world_id,
        series_id=episode.series_id,
        episode_id=episode.episode_id,
        user_request=episode.brief,
        creative_request=episode.title,
        normalized_prompt=episode.brief,
    )
    package = runtime.package_from_generation(context=context, assets=[asset], title=episode.title, prompt_id=prompt.prompt_id)
    evidence = runtime.record_handoff(package=package, handoff=type("H", (), {"handoff_id": "h1", "status": "READY_FOR_XHS"})())
    assert evidence.kind == "XHS_HANDOFF"
    episode = runtime.store.get_episode(episode.episode_id, account_id=account.account_id)
    assert episode.content_status == "HANDOFF_READY"
    nxt = runtime.get_next_action(account_id=account.account_id)
    assert nxt.task_type == "ANALYTICS"


def test_handoff_is_not_publication(runtime, tmp_path):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="handoff", brief="handoff")
    prompt = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="handoff", kind="IMAGE", episode=episode)
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
    kinds = {item.kind for item in runtime.store.list_evidence(account_id=account.account_id)}
    assert "XHS_HANDOFF" in kinds
    assert "PUBLICATION" not in kinds
    assert runtime.store.get_episode(episode.episode_id, account_id=account.account_id).content_status != "PUBLISHED"


def test_analytics_must_bind_episode_and_keeps_nulls(runtime):
    account = _account(runtime)
    with pytest.raises(ConfigurationBlocked):
        runtime.record_analytics(AnalyticsRecord(
            analytics_id=uuid4().hex,
            account_id=account.account_id,
            platform="xiaohongshu",
            likes=3,
        ))
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="a", brief="a")
    saved = runtime.record_analytics(AnalyticsRecord(
        analytics_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        likes=12,
        impressions=None,
        clicks=None,
    ))
    assert saved.impressions is None
    assert saved.clicks is None
    assert saved.likes == 12


def test_learning_requires_provenance_and_stays_isolated(runtime):
    xhs = _account(runtime)
    dy = _seed_account(runtime, platform="douyin", name="B", character="训练角色", world="训练世界", series="训练系列")
    series = runtime.store.active_series(xhs.account_id)
    episode = runtime.continue_series(account_id=xhs.account_id, series_id=series.series_id, title="learn", brief="learn")
    analytics = runtime.record_analytics(AnalyticsRecord(
        analytics_id=uuid4().hex,
        account_id=xhs.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        favorites=40,
    ))
    learning = runtime.record_learning(LearningRecord(
        learning_id=uuid4().hex,
        account_id=xhs.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        analytics_id=analytics.analytics_id,
        what_worked="candid",
        reason="favorites high",
        next_recommendation="keep natural light",
    ))
    assert learning.evidence_status == "NOT_ENOUGH_EVIDENCE"
    assert learning.source_episode_ids == (episode.episode_id,)
    assert runtime.store.list_learning(account_id=dy.account_id, platform="douyin") == []


def test_dashboard_exposes_next_action(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="dash", brief="dash")
    runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="dash", kind="IMAGE", episode=episode)
    board = runtime.dashboard(account_id=account.account_id)
    assert board["account_id"] == account.account_id
    assert board["next_recommended_action"]["task_type"] == "CREATIVE_EXECUTION"
    assert board["pending_creative"]


def test_core_readiness_does_not_require_analytics(runtime):
    account = _account(runtime)
    payload = runtime.production_readiness(account_id=account.account_id, persist=False)
    assert payload["CORE_PRODUCTION"] == "READY"
    assert payload["POST_PRODUCTION"] == "NOT_VERIFIED"
    assert payload["ANALYTICS"] == "NOT_VERIFIED"
    assert payload["LEARNING"] == "NOT_VERIFIED"
    assert payload["FULL_LOOP"] == "NOT_VERIFIED"


def test_accounts_do_not_share_operating_state(runtime):
    a = _account(runtime)
    b = _seed_account(runtime, platform="xiaohongshu", name="B", character="账号B", world="世界B", series="系列B")
    runtime.override_profile(a.account_id, field_name="account_objective", value="A only", reason="isolate")
    profile_b = runtime.store.get_account_profile(b.account_id)
    assert profile_b.account_objective.value != "A only"
    with pytest.raises(IsolationError):
        runtime.store.get_character(a.character_id, account_id=b.account_id)


def test_receipt_model_is_unknown_not_forged(runtime, tmp_path):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="r", brief="r")
    prompt = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="r", kind="IMAGE", episode=episode)
    imported = runtime.import_asset(
        _png(tmp_path, "r.png", 5),
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        asset_role="GENERATED_PRIMARY",
        prompt_id=prompt.prompt_id,
        root=tmp_path / "assets",
    )
    from sqlalchemy import select
    from scripts.db.models import CreativeExecutionReceiptRecord
    with runtime.store._session() as session:
        rows = list(session.execute(select(CreativeExecutionReceiptRecord)).scalars())
    assert rows
    assert rows[0].model == "UNKNOWN"
    assert rows[0].tool == "lechuang"
    assert rows[0].prompt_id == prompt.prompt_id


def test_canonical_analytics_store_constant():
    from content.models import CANONICAL_ANALYTICS_STORE
    assert CANONICAL_ANALYTICS_STORE == "content.models.AnalyticsRecord"


def test_knowledge_field_rejects_unknown_source():
    from content.models import KnowledgeField
    with pytest.raises(ValueError):
        KnowledgeField(value="x", source="FAKE")


def test_task_types_cover_production_chain():
    from content.models import PRODUCTION_CHAIN, TASK_TYPES
    assert all(item in TASK_TYPES for item in PRODUCTION_CHAIN)


def test_seed_sandbox_creates_profile_and_state(runtime):
    seeded = runtime.seed_sandbox()
    xhs = seeded["xiaohongshu"]["account"]
    assert runtime.store.get_account_profile(xhs.account_id) is not None
    assert runtime.store.get_operating_state(xhs.account_id) is not None


def test_doctor_does_not_claim_full_loop_without_evidence(runtime):
    report = runtime.doctor()
    assert report["SYSTEM_CAPABILITY"]["status"] == "PASS"
    assert report["CORE_PRODUCTION"]["status"] == "NOT_CONFIGURED"
    assert report["POST_PRODUCTION"]["status"] == "NOT_VERIFIED"
    assert report["REAL_DAY_1"]["status"] == "NOT_VERIFIED"
    _account(runtime)
    report = runtime.doctor()
    assert report["CORE_PRODUCTION"]["status"] == "READY"
    assert report["PRODUCTION_EVIDENCE"]["status"] == "NOT_VERIFIED"


def test_pattern_promotion_still_fail_closed(runtime):
    account = _account(runtime)
    from content.models import PromptPattern
    with pytest.raises(ConfigurationBlocked):
        runtime.promote_pattern(
            PromptPattern(pattern_id="x", platform="xiaohongshu", account_id=account.account_id, category="CANDID"),
            status="GLOBAL_PATTERN",
            sample_count=1,
        )


def test_no_prompt_reference_exception_allows_import(runtime, tmp_path):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="ex", brief="ex")
    imported = PlatformAssetService(runtime.store).import_asset(
        _png(tmp_path, "ex.png", 9),
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        asset_role="GENERATED_PRIMARY",
        no_prompt_reference=True,
        root=tmp_path / "assets",
    )
    assert imported["status"] == "IMPORTED"
