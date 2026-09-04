from uuid import uuid4

import pytest

from analytics.normalizers.metrics import NormalizedMetrics
from analytics.persistence import CanonicalAnalyticsError, persist_metrics
from content.assets import PlatformAssetService
from content.models import (
    ALLOWED_TASK_TRANSITIONS,
    AnalyticsRecord,
    ConfigurationBlocked,
    CreativeContext,
    ExistingAssetError,
    IsolationError,
    LearningRecord,
)
from content.runtime import ContinuityRuntime
from content.tasks import TaskOS
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


def test_system_capability_is_not_account_ready(runtime):
    payload = runtime.production_readiness(persist=False)
    assert payload["SYSTEM_CAPABILITY"] == "PASS"
    assert payload["ACCOUNT_CONFIGURATION"] == "NOT_CONFIGURED"
    assert payload["CORE_PRODUCTION"] == "NOT_CONFIGURED"
    assert payload["PRODUCTION_EVIDENCE"] == "NOT_VERIFIED"
    assert payload["POST_PRODUCTION"] == "NOT_VERIFIED"
    assert payload["FULL_LOOP"] == "NOT_VERIFIED"


def test_configured_account_is_core_ready_without_evidence(runtime):
    account = _account(runtime)
    payload = runtime.production_readiness(account_id=account.account_id, persist=False)
    assert payload["ACCOUNT_CONFIGURATION"] == "PASS"
    assert payload["CORE_PRODUCTION"] == "READY"
    assert payload["PRODUCTION_EVIDENCE"] == "NOT_VERIFIED"
    assert payload["ANALYTICS"] == "NOT_VERIFIED"
    assert payload["LEARNING"] == "NOT_VERIFIED"
    assert payload["VECTOR"] == "NOT_VERIFIED"
    assert payload["FULL_LOOP"] == "NOT_VERIFIED"


def test_incomplete_account_is_partial_not_ready(runtime):
    account = runtime.create_account(platform="xiaohongshu", display_name="draft")
    payload = runtime.production_readiness(account_id=account.account_id, persist=False)
    assert payload["ACCOUNT_CONFIGURATION"] == "PARTIAL"
    assert payload["CORE_PRODUCTION"] != "READY"


def test_task_chain_and_legal_hops(runtime):
    account = _account(runtime)
    episode, prompt = _compile(runtime, account)
    tasks = runtime.store.list_tasks(account_id=account.account_id, episode_id=episode.episode_id)
    types = [item.task_type for item in tasks]
    assert types[:7] == ["CONTENT_PLAN", "PROMPT_GENERATION", "CREATIVE_EXECUTION", "ASSET_IMPORT", "QA", "PACKAGE", "HANDOFF"]
    plan = next(item for item in tasks if item.task_type == "CONTENT_PLAN")
    creative = next(item for item in tasks if item.task_type == "CREATIVE_EXECUTION")
    assert plan.status == "DONE"
    assert creative.status == "WAITING_OPERATOR"
    history = runtime.store.list_task_history(account_id=account.account_id, task_id=plan.task_id)
    assert history
    assert {item.from_status for item in history} <= set(ALLOWED_TASK_TRANSITIONS) | {plan.status}
    assert all(item.owner and item.created_at for item in history)
    os = TaskOS(runtime.store)
    with pytest.raises(ConfigurationBlocked) as exc:
        os.transition(plan.task_id, to_status="TODO")
    assert exc.value.code == "ILLEGAL_TASK_TRANSITION"
    replica = os.reopen(plan.task_id, reason="重新做")
    assert replica.task_id != plan.task_id
    assert runtime.store.get_task(plan.task_id).status == "DONE"
    assert replica.parent_task_id == plan.task_id


def test_today_buckets_do_not_dump_todo(runtime):
    account = _account(runtime)
    _compile(runtime, account)
    os = TaskOS(runtime.store)
    buckets = os.classify_open_tasks(account_id=account.account_id)
    assert buckets["WAITING_OPERATOR"]
    assert all(item.status != "TODO" for item in os.get_today_tasks(account_id=account.account_id))
    nxt = os.get_next_action(account_id=account.account_id)
    assert nxt is not None
    assert nxt.status != "BLOCKED"
    assert nxt.task_type == "CREATIVE_EXECUTION"


def test_prompt_run_task_binding(runtime):
    account = _account(runtime)
    episode, prompt = _compile(runtime, account)
    stored = runtime.store.get_episode(episode.episode_id, account_id=account.account_id)
    run = runtime.store.get_production_run(stored.production_run_id)
    task = runtime.store.get_task(run.task_id)
    assert run.prompt_id == prompt.prompt_id
    assert task.production_run_id == run.run_id
    assert task.episode_id == run.episode_id == episode.episode_id
    assert prompt.copy_ready and prompt.prompt_hash and prompt.character_id and prompt.world_id


def test_primary_import_receipt_and_existing_asset(runtime, tmp_path):
    account = _account(runtime)
    episode, prompt = _compile(runtime, account)
    path = _png(tmp_path, "day.png", 21)
    imported = runtime.import_asset(
        path,
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        asset_role="GENERATED_PRIMARY",
        prompt_id=prompt.prompt_id,
        root=tmp_path / "assets",
    )
    asset = imported["asset"]
    receipt = runtime.store.get_receipt_for_asset(asset.asset_id)
    run = runtime.store.get_production_run(runtime.store.get_episode(episode.episode_id, account_id=account.account_id).production_run_id)
    assert receipt is not None
    assert receipt.prompt_id == prompt.prompt_id
    assert receipt.production_run_id == run.run_id
    assert receipt.model == "UNKNOWN"
    with pytest.raises(ExistingAssetError):
        PlatformAssetService(runtime.store).import_asset(
            path,
            account_id=account.account_id,
            platform="xiaohongshu",
            episode_id=episode.episode_id,
            asset_role="GENERATED_PRIMARY",
            prompt_id=prompt.prompt_id,
            root=tmp_path / "assets2",
        )


def test_no_prompt_reference_is_audited(runtime, tmp_path):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="ex", brief="ex")
    PlatformAssetService(runtime.store).import_asset(
        _png(tmp_path, "ex.png", 9),
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        asset_role="GENERATED_PRIMARY",
        no_prompt_reference=True,
        no_prompt_reason="operator recovered file",
        operator="op-1",
        root=tmp_path / "assets",
    )
    rows = runtime.store.list_overrides(account.account_id)
    assert rows
    assert rows[0].new_value == "NO_PROMPT_REFERENCE"
    assert rows[0].changed_by == "op-1"
    assert rows[0].reason == "operator recovered file"


def test_package_handoff_does_not_create_publication(runtime, tmp_path):
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
    kinds = {item.kind for item in runtime.store.list_evidence(account_id=account.account_id)}
    assert "XHS_HANDOFF" in kinds
    assert "PUBLICATION" not in kinds
    payload = runtime.production_readiness(account_id=account.account_id, episode_id=episode.episode_id, persist=False)
    assert payload["PRODUCTION_EVIDENCE"] == "PASS"
    assert payload["CORE_PRODUCTION"] == "READY"
    assert payload["ANALYTICS"] == "NOT_VERIFIED"


def test_learning_cannot_verify_without_analytics(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="learn", brief="learn")
    learning = runtime.record_learning(LearningRecord(
        learning_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        what_worked="guess",
        evidence_status="VERIFIED",
    ))
    assert learning.evidence_status == "NOT_ENOUGH_EVIDENCE"


def test_next_prompt_reads_learning_records(runtime):
    account = _account(runtime)
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="a", brief="a")
    analytics = runtime.record_analytics(AnalyticsRecord(
        analytics_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        likes=12,
        impressions=None,
    ))
    runtime.record_learning(LearningRecord(
        learning_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        analytics_id=analytics.analytics_id,
        what_worked="natural light",
        reason="favorites",
        next_recommendation="keep candid street light",
    ))
    concept = runtime.plan_next(account_id=account.account_id, request="咖啡店日常")
    assert not any("candid" in item or "natural" in item for item in concept.learning_basis)
    day2 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="咖啡店日常", brief="咖啡店日常")
    prompt = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="咖啡店日常", kind="IMAGE", episode=day2)
    assert not any("candid" in item or "natural" in item for item in prompt.learning_basis)


def test_world_override_creates_revision(runtime):
    account = _account(runtime)
    world = runtime.override_world(account.account_id, field_name="city", value="深圳南山", reason="以后主要在深圳拍")
    assert world.version == 2
    revisions = runtime.store.list_world_revisions(world.world_id)
    assert [item.version for item in revisions] == [1, 2]


def test_continue_yesterday_creates_new_episode_and_prompt(runtime):
    account = _account(runtime)
    episode, prompt = _compile(runtime, account, title="昨天健身")
    result = runtime.continue_yesterday(account_id=account.account_id, request="继续昨天")
    assert result["episode"].episode_id != episode.episode_id
    assert result["prompt"].prompt_id != prompt.prompt_id
    assert result["character_id"] == account.character_id
    assert result["world_id"] == account.world_id
    assert result["freshness"] == "NEW_PRIMARY_REQUIRED"


def test_change_topic_keeps_character_world(runtime):
    account = _account(runtime)
    _compile(runtime, account, title="健身日常")
    result = runtime.change_topic(account_id=account.account_id, request="换一种咖啡店")
    assert result["character_id"] == account.character_id
    assert result["world_id"] == account.world_id
    assert "咖啡" in result["episode"].title or "咖啡" in result["prompt"].copy_ready


def test_canonical_analytics_fails_closed_without_account():
    with pytest.raises(CanonicalAnalyticsError):
        persist_metrics(NormalizedMetrics(publication_id="p1", values={"platform": "xiaohongshu", "views": 3}))


def test_dashboard_buckets(runtime):
    account = _account(runtime)
    _compile(runtime, account)
    board = runtime.dashboard(account_id=account.account_id)
    assert board["waiting_operator"]
    assert board["next_recommended_action"]["task_type"] == "CREATIVE_EXECUTION"
    assert "today_tasks" in board
    assert "waiting_external" in board
    assert board["recent_prompt"]


def test_accounts_cannot_read_foreign_learning(runtime):
    a = _account(runtime)
    b = _seed_account(runtime, platform="xiaohongshu", name="B", character="账号B", world="世界B", series="系列B")
    series = runtime.store.active_series(a.account_id)
    episode = runtime.continue_series(account_id=a.account_id, series_id=series.series_id, title="a", brief="a")
    analytics = runtime.record_analytics(AnalyticsRecord(
        analytics_id=uuid4().hex,
        account_id=a.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        likes=9,
    ))
    runtime.record_learning(LearningRecord(
        learning_id=uuid4().hex,
        account_id=a.account_id,
        platform="xiaohongshu",
        episode_id=episode.episode_id,
        analytics_id=analytics.analytics_id,
        what_worked="a only",
    ))
    assert runtime.store.list_learning(account_id=b.account_id, platform="xiaohongshu") == []
    with pytest.raises(IsolationError):
        runtime.store.get_character(a.character_id, account_id=b.account_id)
