from uuid import uuid4

import pytest

from content.assets import PlatformAssetService, ReferenceAssetResolver
from content.models import (
    AnalyticsRecord,
    AssetFreshnessError,
    ConfigurationBlocked,
    ContentPackage,
    CreativeContext,
    CrossPlatformAssetReuse,
    ExistingAssetError,
    IsolationError,
    LearningRecord,
    PromptPattern,
)
from content.runtime import ContinuityRuntime
from tests.unit.test_account_continuity import _seed_account
from tests.unit.test_platform_asset_dna import _png


@pytest.fixture
def runtime():
    return ContinuityRuntime.testing()


def test_sandbox_accounts_are_fully_isolated(runtime):
    seeded = runtime.seed_sandbox()
    xhs = seeded["xiaohongshu"]["account"]
    dy = seeded["douyin"]["account"]
    assert xhs.account_id == "meiti-xhs-main"
    assert dy.account_id == "meiti-douyin-main"
    assert xhs.character_id != dy.character_id
    assert xhs.world_id != dy.world_id
    assert runtime.store.get_pool(account_id=xhs.account_id, platform="xiaohongshu").pool_id != runtime.store.get_pool(account_id=dy.account_id, platform="douyin").pool_id
    with pytest.raises(IsolationError):
        runtime.store.get_character(xhs.character_id, account_id=dy.account_id)


def test_day_loop_creates_new_prompt_asset_and_learning(runtime, tmp_path):
    account = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")
    series = runtime.store.active_series(account.account_id)
    day1 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="第一次晨跑", brief="第一次晨跑")
    prompt1 = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="第一次晨跑", kind="IMAGE", episode=day1)
    assert prompt1.copy_ready
    assert prompt1.prompt_hash
    assert prompt1.episode_id == day1.episode_id
    service = PlatformAssetService(runtime.store)
    asset_a = service.import_asset(
        _png(tmp_path, "a.png", 11),
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=day1.episode_id,
        asset_role="GENERATED_PRIMARY",
        prompt_id=prompt1.prompt_id,
        root=tmp_path / "assets",
    )["asset"]
    context = CreativeContext(
        context_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        character_id=account.character_id,
        world_id=account.world_id,
        series_id=day1.series_id,
        episode_id=day1.episode_id,
        user_request=day1.brief,
        creative_request=day1.title,
        normalized_prompt=day1.brief,
    )
    package = runtime.package_from_generation(context=context, assets=[asset_a], title=day1.title, prompt_id=prompt1.prompt_id)
    assert package.primary_assets == (asset_a.asset_id,)
    handoff = runtime.record_handoff(package=package, handoff=type("H", (), {"handoff_id": "h1", "status": "READY_FOR_XHS"})())
    assert handoff.kind == "XHS_HANDOFF"
    analytics = runtime.record_analytics(AnalyticsRecord(
        analytics_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=day1.episode_id,
        package_id=package.package_id,
        handoff_id="h1",
        favorites=40,
        likes=12,
        topic="晨跑",
        prompt_pattern="CANDID_SMARTPHONE_LIFESTYLE",
    ))
    learning = runtime.record_learning(LearningRecord(
        learning_id=uuid4().hex,
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=day1.episode_id,
        analytics_id=analytics.analytics_id,
        what_worked="candid smartphone lifestyle",
        visual_learning="natural light, imperfect frame",
        prompt_learning="CANDID_SMARTPHONE_LIFESTYLE",
        next_recommendation="keep natural light and slight motion",
        reason="Episode 001 favorites were high with candid smartphone lifestyle",
        source_episode_ids=(day1.episode_id,),
    ))
    day2 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="第二天咖啡", brief="继续昨天")
    prompt2 = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="继续昨天 咖啡店", kind="IMAGE", episode=day2, intent="CONTINUE")
    assert prompt2.copy_ready != prompt1.copy_ready
    assert prompt2.scene_prompt != prompt1.scene_prompt
    assert prompt2.parent_prompt_id == prompt1.prompt_id
    assert any("natural light" in item or "candid" in item.lower() for item in prompt2.learning_basis)
    asset_b = service.import_asset(
        _png(tmp_path, "b.png", 90),
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=day2.episode_id,
        asset_role="GENERATED_PRIMARY",
        parent_asset_id=asset_a.asset_id,
        reuse_mode="DERIVED",
        prompt_id=prompt2.prompt_id,
        root=tmp_path / "assets",
    )["asset"]
    assert asset_a.asset_id != asset_b.asset_id
    assert asset_a.sha256 != asset_b.sha256
    day3 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="第三天户外", brief="继续昨天")
    prompt3 = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="继续昨天 户外", kind="IMAGE", episode=day3, intent="CONTINUE")
    asset_c = service.import_asset(
        _png(tmp_path, "c.png", 180),
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=day3.episode_id,
        asset_role="GENERATED_PRIMARY",
        parent_asset_id=asset_b.asset_id,
        reuse_mode="DERIVED",
        prompt_id=prompt3.prompt_id,
        root=tmp_path / "assets",
    )["asset"]
    assert {asset_a.sha256, asset_b.sha256, asset_c.sha256} == {asset_a.sha256, asset_b.sha256, asset_c.sha256}
    assert len({asset_a.sha256, asset_b.sha256, asset_c.sha256}) == 3
    kinds = {item.kind for item in runtime.store.list_evidence(account_id=account.account_id)}
    assert "DAY_001_REAL_ASSET_IMPORTED" in kinds
    assert "DAY_002_REAL_ASSET_IMPORTED" in kinds
    assert "DAY_003_REAL_ASSET_IMPORTED" in kinds
    assert learning.reason


def test_same_sha_cannot_bind_second_identity(runtime, tmp_path):
    account = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")
    episode = runtime.continue_series(account_id=account.account_id, series_id=runtime.store.active_series(account.account_id).series_id, title="Day 1", brief="第一次")
    path = _png(tmp_path, "same.png", 7)
    service = PlatformAssetService(runtime.store)
    first = service.import_asset(path, account_id=account.account_id, platform="xiaohongshu", episode_id=episode.episode_id, asset_role="GENERATED_PRIMARY", root=tmp_path / "assets")
    with pytest.raises(ExistingAssetError) as exc:
        service.import_asset(path, account_id=account.account_id, platform="xiaohongshu", episode_id=episode.episode_id, asset_role="GENERATED_PRIMARY", root=tmp_path / "assets")
    assert exc.value.code == "EXISTING_ASSET"
    loaded = runtime.store.get_asset_by_sha256(first["asset"].sha256)
    assert loaded.asset_id == first["asset"].asset_id


def test_cross_platform_primary_blocked_explicit_reference_allowed(runtime, tmp_path):
    xhs = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")
    dy = _seed_account(runtime, platform="douyin", name="B", character="训练角色", world="训练世界", series="训练系列")
    xhs_ep = runtime.continue_series(account_id=xhs.account_id, series_id=runtime.store.active_series(xhs.account_id).series_id, title="X1", brief="x")
    dy_ep = runtime.continue_series(account_id=dy.account_id, series_id=runtime.store.active_series(dy.account_id).series_id, title="D1", brief="d")
    service = PlatformAssetService(runtime.store)
    xhs_asset = service.import_asset(_png(tmp_path, "xhs.png", 33), account_id=xhs.account_id, platform="xiaohongshu", episode_id=xhs_ep.episode_id, asset_role="GENERATED_PRIMARY", root=tmp_path / "assets")["asset"]
    package = ContentPackage(package_id=uuid4().hex, title="dy", body="dy", account_id=dy.account_id, platform="douyin", episode_id=dy_ep.episode_id)
    with pytest.raises(CrossPlatformAssetReuse):
        service.map_package_asset(package, xhs_asset, role="PRIMARY")
    mapping = service.map_package_asset(package, xhs_asset, role="REFERENCE")
    assert mapping.role == "REFERENCE"
    auto = ReferenceAssetResolver(runtime.store).resolve(account_id=dy.account_id, platform="douyin", previous_episode=xhs_ep)
    assert all(item.asset_id != xhs_asset.asset_id for item in auto)
    explicit = ReferenceAssetResolver(runtime.store).resolve(account_id=dy.account_id, platform="douyin", explicit=(xhs_asset.asset_id,))
    assert explicit and explicit[0].asset_role == "CHARACTER_REFERENCE"


def test_learning_does_not_cross_platforms(runtime):
    xhs = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="世界A", series="系列A")
    dy = _seed_account(runtime, platform="douyin", name="B", character="训练角色", world="世界B", series="系列B")
    runtime.record_learning(LearningRecord(
        learning_id=uuid4().hex,
        account_id=xhs.account_id,
        platform="xiaohongshu",
        what_worked="XHS only candid",
        next_recommendation="XHS natural light",
        reason="XHS Episode 001 favorites",
    ))
    xhs_rows = runtime.store.list_learning(account_id=xhs.account_id, platform="xiaohongshu")
    dy_rows = runtime.store.list_learning(account_id=dy.account_id, platform="douyin")
    assert xhs_rows and xhs_rows[0].what_worked == "XHS only candid"
    assert dy_rows == []
    with pytest.raises(ConfigurationBlocked):
        runtime.promote_pattern(
            PromptPattern(pattern_id="xhs-candid", platform="xiaohongshu", account_id=xhs.account_id, category="CANDID"),
            status="GLOBAL_PATTERN",
            sample_count=1,
        )


def test_prompt_character_world_versions_are_immutable(runtime):
    account = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")
    series = runtime.store.active_series(account.account_id)
    day1 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="V1", brief="第一版")
    first = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="第一版", kind="IMAGE", episode=day1)
    stored = runtime.store.get_prompt(first.prompt_id)
    assert stored.copy_ready == first.copy_ready
    day2 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="V2", brief="第二版")
    second = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="第二版不同场景", kind="IMAGE", episode=day2, intent="CONTINUE")
    assert second.prompt_id != first.prompt_id
    assert runtime.store.get_prompt(first.prompt_id).copy_ready == first.copy_ready
    character = runtime.store.get_character(account.character_id, account_id=account.account_id)
    world = runtime.store.get_world(account.world_id, account_id=account.account_id)
    assert character.version == 1
    assert world.version == 1
    episode = runtime.store.get_episode(day1.episode_id, account_id=account.account_id)
    assert episode.prompt_id == first.prompt_id


def test_duplicate_prompt_is_rejected(runtime):
    account = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")
    series = runtime.store.active_series(account.account_id)
    day1 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="同一天", brief="同一天")
    first = runtime.compile_prompt(account_id=account.account_id, platform="xiaohongshu", request="同一天", kind="IMAGE", episode=day1)
    day2 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="同一天", brief="同一天")
    with pytest.raises(AssetFreshnessError) as exc:
        from content.compiler import PromptCompiler
        PromptCompiler(runtime.store).compile(
            account_id=account.account_id,
            platform="xiaohongshu",
            request="同一天",
            kind="IMAGE",
            character=runtime.store.get_character(account.character_id, account_id=account.account_id),
            world=runtime.store.get_world(account.world_id, account_id=account.account_id),
            series=series,
            episode=day2,
            previous_prompt=first,
            intent="CONTINUE",
        )
    assert exc.value.code == "DUPLICATE_CONTENT"


def test_doctor_does_not_claim_real_days_without_evidence(runtime):
    report = runtime.doctor()
    assert report["REAL_DAY_1"]["status"] == "NOT_VERIFIED"
    assert report["REAL_DAY_2"]["status"] == "NOT_VERIFIED"
    assert report["REAL_DAY_3"]["status"] == "NOT_VERIFIED"
    assert report["ANALYTICS_RUNTIME"]["lane"] == "PRODUCTION_EVIDENCE"
    assert report["PROMPT_COMPILER"]["lane"] == "ARCHITECTURE"
