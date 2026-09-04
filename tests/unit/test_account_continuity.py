from types import SimpleNamespace
from uuid import uuid4

import pytest

from content.models import (
    AccountWorld,
    ContinuityError,
    IsolationError,
    PerformanceFeedback,
    VirtualCharacter,
)
from content.runtime import ContinuityRuntime
from content.resolve import IntentResolver


def _character(account_id: str, name: str, **fields) -> VirtualCharacter:
    return VirtualCharacter(
        character_id=uuid4().hex,
        account_id=account_id,
        name=name,
        gender=fields.get("gender", "male"),
        age_range=fields.get("age_range", "24-28"),
        clothing_profile=fields.get("clothing_profile", {"style": "casual"}),
        personality_profile=fields.get("personality_profile", {"energy": "high"}),
        forbidden_changes=("drastic hairstyle changes", "unexplained age changes"),
        visual_identity_rules={"keep_face_consistent": True},
    )


def _world(account_id: str, name: str, **fields) -> AccountWorld:
    return AccountWorld(
        world_id=uuid4().hex,
        account_id=account_id,
        name=name,
        world_description=fields.get("world_description", name),
        core_theme=fields.get("core_theme", name),
        values=fields.get("values", ("真实",)),
        tone=fields.get("tone", "relaxed"),
        visual_language=fields.get("visual_language", {"light": "natural"}),
        audience=fields.get("audience", "lifestyle"),
    )


def _seed_account(runtime: ContinuityRuntime, *, platform: str, name: str, character: str, world: str, series: str, extras: dict | None = None):
    extras = dict(extras or {})
    account = runtime.create_account(platform=platform, display_name=name, account_id=f"{platform}-{name}")
    character_fields = {key: extras[key] for key in ("gender", "age_range", "clothing_profile", "personality_profile") if key in extras}
    world_fields = {key: extras[key] for key in ("world_description", "core_theme", "values", "tone", "visual_language", "audience") if key in extras}
    runtime.bind_character(account.account_id, _character(account.account_id, character, **character_fields))
    runtime.bind_world(account.account_id, _world(account.account_id, world, **world_fields))
    runtime.create_series(account_id=account.account_id, name=series)
    return runtime.store.activate_account(account.account_id)


@pytest.fixture
def runtime():
    return ContinuityRuntime.testing()


def test_accounts_and_characters_are_isolated(runtime):
    xhs_a = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天重新找回生活状态")
    xhs_b = _seed_account(runtime, platform="xiaohongshu", name="B", character="账号B角色", world="另一个小红书世界", series="B系列")
    dy_a = _seed_account(runtime, platform="douyin", name="A", character="训练角色", world="高能量训练", series="训练挑战")
    dy_b = _seed_account(runtime, platform="douyin", name="B", character="抖音B", world="抖音世界B", series="抖音B系列")
    assert xhs_a.account_id != xhs_b.account_id
    assert xhs_a.account_id != dy_a.account_id
    assert xhs_a.character_id != xhs_b.character_id
    assert xhs_a.character_id != dy_a.character_id
    with pytest.raises(IsolationError):
        runtime.store.get_character(xhs_a.character_id, account_id=xhs_b.account_id)
    with pytest.raises(IsolationError):
        runtime.store.get_character(xhs_a.character_id, account_id=dy_a.account_id)
    with pytest.raises(IsolationError):
        runtime.store.get_world(xhs_a.world_id, account_id=dy_b.account_id)
    with pytest.raises(IsolationError):
        runtime.store.get_series(runtime.store.active_series(xhs_a.account_id).series_id, account_id=dy_a.account_id)


def test_continuity_reads_previous_episode_and_fails_when_gap(runtime):
    account = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天重新找回生活状态")
    series = runtime.store.active_series(account.account_id)
    day1 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, brief="第一次晨跑", title="第一次晨跑")
    day2 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, brief="昨天第一次跑完，今天继续", title="第二天")
    day3 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, brief="开始形成习惯", title="第三天")
    assert day2.previous_episode_id == day1.episode_id
    assert day3.previous_episode_id == day2.episode_id
    assert runtime.engine.get_previous_episode(day2).episode_id == day1.episode_id
    assert runtime.engine.get_previous_episode(day3).episode_id == day2.episode_id
    runtime.store.delete_episode(day2.episode_id)
    with pytest.raises(ContinuityError):
        runtime.engine.get_previous_episode(runtime.store.get_episode(day3.episode_id, account_id=account.account_id))
    with pytest.raises(ContinuityError):
        runtime.continue_series(account_id=account.account_id, series_id=series.series_id, brief="第四天")


def test_platform_packages_are_independent(runtime):
    xhs = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天重新找回生活状态")
    douyin = _seed_account(
        runtime,
        platform="douyin",
        name="B",
        character="高能训练者",
        world="高能量男性训练",
        series="训练挑战",
        extras={"visual_language": {"motion": "strong first 3 seconds"}, "tone": "high-energy"},
    )
    xhs_prep = runtime.prepare("给我做今天的小红书和抖音版本。第一次晨跑", platform="xiaohongshu")
    dy_prep = runtime.prepare("给我做今天的小红书和抖音版本。第一次晨跑", platform="douyin")
    xhs_pkg = runtime.package_from_generation(context=xhs_prep["context"], assets=[], title="第一次晨跑")
    dy_pkg = runtime.package_from_generation(context=dy_prep["context"], assets=[], title="第一次晨跑")
    assert xhs_pkg.package_id != dy_pkg.package_id
    assert xhs_pkg.platform == "xiaohongshu"
    assert dy_pkg.platform == "douyin"
    assert xhs_pkg.content_type != dy_pkg.content_type
    assert xhs_pkg.character_id == xhs.character_id
    assert dy_pkg.character_id == douyin.character_id
    assert xhs_pkg.world_id == xhs.world_id
    assert dy_pkg.world_id == douyin.world_id
    assert xhs_pkg.metadata["character_context"]["name"] != dy_pkg.metadata["character_context"]["name"]
    assert xhs_pkg.metadata["world_context"]["name"] != dy_pkg.metadata["world_context"]["name"]
    assert xhs_pkg.metadata["platform_policy"]["visual"] != dy_pkg.metadata["platform_policy"]["visual"]


def test_asset_lineage_and_revisions_are_immutable(runtime):
    account = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天重新找回生活状态")
    prepared = runtime.prepare("继续昨天的小红书系列")
    context = prepared["context"]
    first = SimpleNamespace(asset_id="image_012_v1", path="/tmp/image_012_v1.png")
    second = SimpleNamespace(asset_id="image_012_v2", path="/tmp/image_012_v2.png")
    package = runtime.package_from_generation(context=context, assets=[first], title="Day 1", package_id="pkg-lineage")
    lineage1 = runtime.record_lineage(asset=first, context=context, provider="xiaole-lechuang", provider_task_id="task-1", model="gpt-image-2", package_id=package.package_id)
    lineage2 = runtime.record_lineage(asset=second, context=context, parent_asset_id=first.asset_id, provider="xiaole-lechuang", provider_task_id="task-2", model="gpt-image-2", package_id=package.package_id)
    runtime.package_from_generation(context=context, assets=[second], title="Day 1 v2", package_id="pkg-lineage", status="GENERATED")
    assert lineage1.asset_id != lineage2.asset_id
    assert lineage2.attempt_no > lineage1.attempt_no
    assert runtime.store.get_lineage("image_012_v1", account_id=account.account_id).account_id == account.account_id
    revisions = runtime.store.list_revisions("pkg-lineage")
    assert len(revisions) == 2
    assert revisions[0].snapshot["media_assets"] != revisions[1].snapshot["media_assets"]
    assert revisions[1].parent_revision_id == revisions[0].revision_id


def test_cli_continue_resolves_xiaohongshu_series(runtime):
    account = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天重新找回生活状态")
    series = runtime.store.active_series(account.account_id)
    runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="第一次晨跑", brief="第一次晨跑")
    target = IntentResolver(runtime.store).resolve("继续昨天的小红书系列")
    assert target.platform == "xiaohongshu"
    assert target.account_id == account.account_id
    assert target.series_id == series.series_id
    assert target.reason in {"active_account_context", "named_account", "platform_only"}
    prepared = runtime.prepare("继续昨天的小红书系列")
    assert prepared["episode"].episode_no == 2
    assert prepared["episode"].previous_episode_id
    assert prepared["context"].resolved_target["reason"]
    named = IntentResolver(runtime.store).resolve("给小红书账号A做今天的内容。")
    assert named.account_id == account.account_id


def test_cross_account_guard_blocks_foreign_character(runtime):
    xhs = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")
    douyin = _seed_account(runtime, platform="douyin", name="B", character="训练角色", world="训练世界", series="训练系列")
    with pytest.raises(IsolationError):
        runtime.isolation.assert_owned(account_id=xhs.account_id, character_id=douyin.character_id)
    prepared = runtime.prepare("给抖音也做一版，但不要和小红书一样，要符合抖音账号自己的角色和风格。")
    assert prepared["account"].account_id == douyin.account_id
    assert prepared["context"].character_id == douyin.character_id
    assert prepared["isolation"]["decision"] == "pass"
    assert prepared["character_qa"]["decision"] == "pass"


def test_publication_writeback_and_feedback(runtime):
    _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")
    prepared = runtime.prepare("给我生成今天的小红书内容。")
    package = runtime.package_from_generation(context=prepared["context"], assets=[SimpleNamespace(asset_id="asset-1", path="/tmp/a.png")])
    runtime.record_lineage(asset=SimpleNamespace(asset_id="asset-1"), context=prepared["context"], package_id=package.package_id, provider="xiaole-lechuang")
    runtime.record_publication(package=package, publication=SimpleNamespace(
        publication_id="pub-1",
        provider_post_id="ext-1",
        published_at="2026-09-04T00:00:00+00:00",
        platform="xiaohongshu",
        external_url="https://example.invalid/post/1",
    ))
    episode = runtime.store.get_episode(package.episode_id, account_id=package.account_id)
    assert episode.content_status == "PUBLISHED"
    published = [item for item in runtime.store.list_memories(account_id=package.account_id, kind="episode") if item.key == "published"]
    assert published[-1].value["external_post_id"] == "ext-1"
    assert published[-1].value["publication_id"] == "pub-1"
    lineage = runtime.store.get_lineage("asset-1", account_id=package.account_id)
    assert lineage.published is True
    feedback = runtime.record_feedback(PerformanceFeedback(
        feedback_id=uuid4().hex,
        account_id=package.account_id,
        platform="xiaohongshu",
        content_package_id=package.package_id,
        topic="晨跑",
        engagement={"likes": 1},
    ))
    assert runtime.store.list_feedback(package.account_id)[-1].feedback_id == feedback.feedback_id
    calendar = runtime.calendar()
    assert calendar[0]["published"] is True


def test_named_account_and_active_reason_are_recorded(runtime):
    first = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="世界A", series="系列A")
    _seed_account(runtime, platform="xiaohongshu", name="B", character="角色B", world="世界B", series="系列B")
    runtime.store.activate_account(first.account_id)
    silent = IntentResolver(runtime.store).resolve("继续昨天")
    assert silent.account_id == first.account_id
    assert silent.reason == "active_account_context"
    named = IntentResolver(runtime.store).resolve("给小红书账号B做今天的内容。")
    assert named.account_id.endswith("B")
    assert named.reason == "named_account"


def test_cli_surface_has_continuity_commands():
    from pathlib import Path

    source = Path("scripts/meiti.py").read_text(encoding="utf-8")
    for token in (
        'creative_sub.add_parser("continue")',
        'creative_sub.add_parser("series")',
        'creative_sub.add_parser("history")',
        'creative_sub.add_parser("inspect")',
        'creative_sub.add_parser("lineage")',
        'creative_sub.add_parser("image-to-video")',
        'sub.add_parser("account")',
        'content_sub.add_parser("calendar")',
    ):
        assert token in source
