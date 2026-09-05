from uuid import uuid4

import pytest

from content.models import ConfigurationBlocked, CreatorAccount, IsolationError, KnowledgeField, ProductionMemory
from content.planner import CreatorBrain, CreatorStrategyService
from content.runtime import ContinuityRuntime
from tests.unit.test_account_continuity import _seed_account


@pytest.fixture
def runtime():
    return ContinuityRuntime.testing()


def _account(runtime, name="A"):
    return _seed_account(runtime, platform="xiaohongshu", name=name, character="张满血", world="深圳认真生活", series="30天系列")


def test_creator_account_alias_and_no_login_ready(runtime):
    account = runtime.create_account(platform="xiaohongshu", display_name="no-login")
    assert isinstance(account, CreatorAccount)
    connection = runtime.store.get_platform_connection(account.account_id, account.platform)
    assert connection is not None
    assert connection.connection_status == "NOT_CONNECTED"
    assert runtime.store.current_strategy(account.account_id) is not None
    assert runtime.store.get_creator_state(account.account_id) is not None
    payload = runtime.production_readiness(account_id=account.account_id, persist=False)
    assert payload["CORE_PRODUCTION"] != "READY"
    assert payload["CORE_CONTENT_PRODUCTION"] != "READY"
    assert payload["EXTERNAL_CONNECTION"] == "NOT_CONNECTED"


def test_configured_no_login_account_is_core_ready(runtime):
    account = _account(runtime)
    connection = runtime.store.get_platform_connection(account.account_id, account.platform)
    assert connection.connection_status == "NOT_CONNECTED"
    payload = runtime.production_readiness(account_id=account.account_id, persist=False)
    assert payload["CORE_PRODUCTION"] == "READY"
    assert payload["CORE_CONTENT_PRODUCTION"] == "READY"
    assert payload["ANALYTICS"] == "NOT_VERIFIED"
    assert payload["LEARNING"] == "NOT_VERIFIED"


def test_unknown_fields_are_not_user_defined(runtime):
    account = runtime.create_account(platform="xiaohongshu", display_name="unknowns")
    assert account.target_audience.source == "UNKNOWN"
    assert account.commercial_direction.certainty == "UNKNOWN"
    saved = runtime.configure_identity(
        account.account_id,
        positioning="认真生活记录",
        account_subject="个人创作者",
        target_audience="都市年轻女性",
        reason="operator setup",
    )
    assert saved.positioning.source == "USER_DEFINED"
    assert saved.commercial_direction.source == "UNKNOWN"
    prompt_account = runtime.store.get_account(saved.account_id)
    assert prompt_account.known("positioning")
    assert not prompt_account.known("commercial_direction")


def test_strategy_revision_requires_reason_and_is_not_silent(runtime):
    account = _account(runtime)
    service = CreatorStrategyService(runtime.store)
    first = service.ensure_default(account)
    with pytest.raises(ConfigurationBlocked):
        service.revise(account.account_id, why_changed="", objective="growth")
    second = service.revise(account.account_id, why_changed="tighten positioning", positioning="真实生活切片")
    assert second.version == first.version + 1
    assert second.supersedes_strategy_id == first.strategy_id
    rows = runtime.store.list_strategies(account.account_id)
    statuses = {item.strategy_id: item.status for item in rows}
    assert statuses[first.strategy_id] == "SUPERSEDED"
    assert statuses[second.strategy_id] == "ACTIVE"


def test_today_and_continue_yesterday_create_decision_trace(runtime):
    account = _account(runtime)
    runtime.configure_identity(
        account.account_id,
        positioning="认真生活",
        account_subject="个人创作者",
        content_pillars=("日常记录", "人物状态", "生活场景", "Experiment"),
        reason="seed",
    )
    day1 = runtime.today(account_id=account.account_id, request="今天做什么")
    assert day1["CORE_CONTENT_PRODUCTION"] == "READY"
    assert day1["CONNECTION"] == "NOT_CONNECTED"
    assert day1["EPISODE"]["episode_no"] == 1
    assert day1["PROMPT"]["copy_ready"]
    prompt1 = runtime.store.get_prompt(day1["PROMPT"]["prompt_id"])
    assert "CREATOR STRATEGY BASIS" in prompt1.copy_ready
    assert "CONTENT DECISION" in prompt1.copy_ready
    assert "NOVELTY BASIS" in prompt1.copy_ready
    day2 = runtime.continue_yesterday(account_id=account.account_id, request="继续昨天")
    assert day2["episode"].episode_id != day1["EPISODE"]["episode_id"]
    assert day2["prompt"].prompt_id != day1["PROMPT"]["prompt_id"]
    assert day2["episode"].content_decision_id != day1["EPISODE"]["content_decision_id"]
    assert day2["prompt"].copy_ready != prompt1.copy_ready
    memories = runtime.store.list_production_memories(account.account_id)
    assert len(memories) == 2
    assert {item.status for item in memories} <= {"CURRENT", "HISTORICAL", "SUPERSEDED"}
    assert sum(1 for item in memories if item.status == "CURRENT") == 1


def test_day3_uses_day1_and_day2_memory(runtime):
    account = _account(runtime)
    first = runtime.produce_today(account_id=account.account_id, request="清晨出门")
    second = runtime.continue_yesterday(account_id=account.account_id, request="继续昨天")
    third = runtime.continue_yesterday(account_id=account.account_id, request="继续昨天")
    state = runtime.store.get_creator_state(account.account_id)
    assert first["episode"].episode_no == 1
    assert second["episode"].episode_no == 2
    assert third["episode"].episode_no == 3
    assert first["decision"].selected_topic in state.recent_topics
    assert second["decision"].selected_topic in state.recent_topics
    assert third["prompt"].copy_ready != first["prompt"].copy_ready
    assert third["prompt"].copy_ready != second["prompt"].copy_ready
    assert "do_not_repeat" in " ".join(third["prompt"].continuity_basis) or third["decision"].avoids


def test_idea_accept_modify_reject(runtime):
    account = _account(runtime)
    runtime.configure_identity(
        account.account_id,
        positioning="认真生活记录",
        forbidden_topics=("带货话术",),
        reason="seed",
    )
    accepted = CreatorBrain(runtime.store).decide(account_id=account.account_id, request="夜跑后的真实生活", persist=False)
    assert accepted.idea_decision in {"ACCEPT", "MODIFY"}
    rejected = CreatorBrain(runtime.store).decide(account_id=account.account_id, request="带货话术专场", persist=False)
    assert rejected.idea_decision == "REJECT"
    produced = runtime.produce_today(account_id=account.account_id, request="带货话术专场")
    assert produced["episode"] is None
    assert produced["status"] == "REJECT"


def test_seven_day_anti_collapse(runtime):
    account = _account(runtime)
    topics = []
    scenes = []
    angles = []
    hooks = []
    prompts = []
    for _ in range(7):
        planned = runtime.produce_today(account_id=account.account_id, request="继续昨天", intent="CONTINUE")
        decision = planned["decision"]
        topics.append(decision.selected_topic)
        scenes.append(decision.selected_scene)
        angles.append(decision.selected_angle)
        hooks.append(decision.selected_hook)
        prompts.append(planned["prompt"].copy_ready)
    assert len(set(topics)) > 1
    assert len(set(scenes)) > 1
    assert len(set(angles)) > 1
    assert len(set(hooks)) > 1
    assert len(set(prompts)) == 7
    assert not all(item == topics[0] for item in topics)
    assert not all(item == scenes[0] for item in scenes)


def test_memory_conflict_prefers_latest_current(runtime):
    account = _account(runtime)
    brain = CreatorBrain(runtime.store)
    older = brain.memory.record(ProductionMemory(
        memory_id=uuid4().hex,
        account_id=account.account_id,
        platform=account.platform,
        status="CURRENT",
        what_was_produced="暖色视觉",
        next_direction="继续暖色",
        importance=0.4,
        confidence=0.4,
        effective_from="2026-08-01T00:00:00",
    ))
    newer = brain.memory.record(ProductionMemory(
        memory_id=uuid4().hex,
        account_id=account.account_id,
        platform=account.platform,
        status="CURRENT",
        episode_id="ep-new",
        what_was_produced="冷色视觉",
        next_direction="改冷色",
        importance=0.9,
        confidence=0.9,
        effective_from="2026-09-01T00:00:00",
        supersedes_id=older.memory_id,
    ))
    resolved = brain.memory.resolve_conflict(runtime.store.list_production_memories(account.account_id))
    assert resolved.memory_id == newer.memory_id
    live = runtime.store.list_production_memories(account.account_id, status="CURRENT")
    assert [item.memory_id for item in live] == [newer.memory_id]


def test_oauth_missing_does_not_block_identity_resolver(runtime):
    account = _account(runtime)
    from content.resolve import IntentResolver
    target = IntentResolver(runtime.store).resolve("继续昨天", account_id=account.account_id)
    assert target.account_id == account.account_id
    connection = runtime.store.get_platform_connection(account.account_id, account.platform)
    assert connection.connection_status == "NOT_CONNECTED"
