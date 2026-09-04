from pathlib import Path
from uuid import uuid4

import pytest

from content.assets import AssetFreshnessGuard, PlatformAssetService, ReferenceAssetResolver
from content.compiler import PromptCompiler
from content.models import (
    AssetFreshnessError,
    ContentPackage,
    CrossPlatformAssetReuse,
    ExistingAssetError,
    PromptPattern,
)
from content.runtime import ContinuityRuntime
from creative.schemas import MediaAsset
from tests.unit.test_account_continuity import _seed_account


@pytest.fixture
def runtime():
    return ContinuityRuntime.testing()


def _png(tmp_path: Path, name: str, color: int) -> Path:
    from PIL import Image

    path = tmp_path / name
    Image.new("RGB", (8, 8), (color, 40, 80)).save(path)
    return path


def test_each_platform_account_has_independent_character_world_and_pool(runtime):
    xhs = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")
    dy = _seed_account(runtime, platform="douyin", name="A", character="训练角色", world="训练世界", series="训练系列")
    assert xhs.character_id != dy.character_id
    assert xhs.world_id != dy.world_id
    xhs_pool = runtime.store.get_pool(account_id=xhs.account_id, platform="xiaohongshu")
    dy_pool = runtime.store.get_pool(account_id=dy.account_id, platform="douyin")
    assert xhs_pool is not None and dy_pool is not None
    assert xhs_pool.pool_id != dy_pool.pool_id
    assert runtime.store.get_creative_dna(xhs.account_id, "xiaohongshu").platform == "xiaohongshu"
    assert runtime.store.get_creative_dna(dy.account_id, "douyin").platform == "douyin"


def test_freshness_guard_blocks_same_sha_and_reference_primary():
    previous = MediaAsset(asset_id="a", type="image", path="a.png", sha256="abc", account_id="acc", platform="xiaohongshu", asset_role="GENERATED_PRIMARY")
    candidate = MediaAsset(asset_id="b", type="image", path="b.png", sha256="abc", account_id="acc", platform="xiaohongshu", asset_role="GENERATED_PRIMARY")
    result = AssetFreshnessGuard().inspect(
        current_episode=None,
        candidate=candidate,
        previous_asset=previous,
        platform="xiaohongshu",
        account_id="acc",
        intent="CREATE",
    )
    assert result["decision"] == "FAIL"
    assert result["code"] == "SAME_FILE_REUSE"
    with pytest.raises(AssetFreshnessError) as exc:
        AssetFreshnessGuard().assert_fresh(
            current_episode=None,
            candidate=MediaAsset(asset_id="r", type="image", path="r.png", sha256="zzz", account_id="acc", platform="xiaohongshu", asset_role="CHARACTER_REFERENCE"),
            platform="xiaohongshu",
            account_id="acc",
        )
    assert exc.value.code == "REFERENCE_AS_PRIMARY"


def test_import_same_file_is_existing_asset_not_new_id(runtime, tmp_path):
    account = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")
    episode = runtime.continue_series(account_id=account.account_id, series_id=runtime.store.active_series(account.account_id).series_id, title="Day 1", brief="第一次晨跑")
    path = _png(tmp_path, "day1.png", 12)
    service = PlatformAssetService(runtime.store)
    first = service.import_asset(path, account_id=account.account_id, platform="xiaohongshu", episode_id=episode.episode_id, asset_role="GENERATED_PRIMARY", no_prompt_reference=True, root=tmp_path / "assets")
    with pytest.raises(ExistingAssetError) as exc:
        service.import_asset(path, account_id=account.account_id, platform="xiaohongshu", episode_id=episode.episode_id, asset_role="GENERATED_PRIMARY", no_prompt_reference=True, root=tmp_path / "assets")
    assert exc.value.code == "EXISTING_ASSET"
    assert first["asset"].sha256 in str(exc.value)


def test_next_episode_requires_new_primary_and_allows_derived(runtime, tmp_path):
    account = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")
    series = runtime.store.active_series(account.account_id)
    day1 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="Day 1", brief="第一次晨跑")
    service = PlatformAssetService(runtime.store)
    first = service.import_asset(
        _png(tmp_path, "day1.png", 20),
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=day1.episode_id,
        asset_role="GENERATED_PRIMARY",
        no_prompt_reference=True,
        root=tmp_path / "assets",
    )
    day2 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="Day 2", brief="继续昨天")
    stale = MediaAsset(
        asset_id=first["asset"].asset_id,
        type="image",
        path=first["asset"].path,
        sha256=first["asset"].sha256,
        account_id=account.account_id,
        platform="xiaohongshu",
        asset_role="GENERATED_PRIMARY",
    )
    with pytest.raises(AssetFreshnessError) as stale_exc:
        AssetFreshnessGuard().assert_fresh(
            current_episode=day2,
            candidate=stale,
            previous_episode=day1,
            previous_asset=first["asset"],
            platform="xiaohongshu",
            account_id=account.account_id,
            intent="CONTINUE",
        )
    assert stale_exc.value.code in {"STALE_ASSET_REUSE", "SAME_FILE_REUSE"}
    second = service.import_asset(
        _png(tmp_path, "day2.png", 90),
        account_id=account.account_id,
        platform="xiaohongshu",
        episode_id=day2.episode_id,
        asset_role="GENERATED_PRIMARY",
        parent_asset_id=first["asset"].asset_id,
        reuse_mode="DERIVED",
        no_prompt_reference=True,
        root=tmp_path / "assets",
    )
    assert second["asset"].sha256 != first["asset"].sha256
    assert second["lineage"].parent_asset_id == first["asset"].asset_id
    assert second["lineage"].reuse_mode == "DERIVED"
    assert runtime.store.get_episode(day2.episode_id, account_id=account.account_id).primary_asset_id == second["asset"].asset_id


def test_cross_platform_primary_is_blocked_but_reference_is_allowed(runtime, tmp_path):
    xhs = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")
    dy = _seed_account(runtime, platform="douyin", name="B", character="训练角色", world="训练世界", series="训练系列")
    xhs_ep = runtime.continue_series(account_id=xhs.account_id, series_id=runtime.store.active_series(xhs.account_id).series_id, title="XHS1", brief="小红书日常")
    dy_ep = runtime.continue_series(account_id=dy.account_id, series_id=runtime.store.active_series(dy.account_id).series_id, title="DY1", brief="抖音日常")
    service = PlatformAssetService(runtime.store)
    xhs_asset = service.import_asset(
        _png(tmp_path, "xhs.png", 30),
        account_id=xhs.account_id,
        platform="xiaohongshu",
        episode_id=xhs_ep.episode_id,
        asset_role="GENERATED_PRIMARY",
        no_prompt_reference=True,
        root=tmp_path / "assets",
    )["asset"]
    package = ContentPackage(package_id=uuid4().hex, title="dy", body="dy", account_id=dy.account_id, platform="douyin", episode_id=dy_ep.episode_id)
    with pytest.raises(CrossPlatformAssetReuse):
        service.map_package_asset(package, xhs_asset, role="PRIMARY")
    mapping = service.map_package_asset(package, xhs_asset, role="REFERENCE")
    assert mapping.role == "REFERENCE"
    refs = ReferenceAssetResolver(runtime.store).resolve(
        account_id=dy.account_id,
        platform="douyin",
        previous_episode=xhs_ep,
        explicit=(xhs_asset.asset_id,),
        allow_global=True,
    )
    assert refs
    with pytest.raises(AssetFreshnessError):
        ReferenceAssetResolver(runtime.store).as_primary(refs[0])


def test_prompt_compiler_outputs_copy_ready_and_rejects_duplicate_scene(runtime):
    account = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="深圳认真生活", series="30天系列")
    series = runtime.store.active_series(account.account_id)
    day1 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="第一次晨跑", brief="第一次晨跑")
    character = runtime.store.get_character(account.character_id, account_id=account.account_id)
    world = runtime.store.get_world(account.world_id, account_id=account.account_id)
    compiler = PromptCompiler(runtime.store)
    first = compiler.compile(
        account_id=account.account_id,
        platform="xiaohongshu",
        request="第一次晨跑",
        kind="IMAGE",
        character=character,
        world=world,
        series=series,
        episode=day1,
    )
    assert "COPY READY" in first.copy_ready
    assert "IMAGE PROMPT PACKAGE" in first.copy_ready
    assert "CHARACTER LOCK" in first.copy_ready
    assert "WORLD LOCK" in first.copy_ready
    day2 = runtime.continue_series(account_id=account.account_id, series_id=series.series_id, title="第二天", brief="继续昨天")
    second = compiler.compile(
        account_id=account.account_id,
        platform="xiaohongshu",
        request="继续昨天",
        kind="IMAGE",
        character=character,
        world=world,
        series=series,
        episode=day2,
        previous=day1,
        previous_prompt=first,
        intent="CONTINUE",
    )
    assert second.scene_prompt != first.scene_prompt
    video = compiler.compile(
        account_id=account.account_id,
        platform="xiaohongshu",
        request="图生视频",
        kind="IMAGE_TO_VIDEO",
        character=character,
        world=world,
        series=series,
        episode=day2,
        source_asset_id="src-1",
    )
    assert "IMAGE_TO_VIDEO PACKAGE" in video.copy_ready
    assert video.source_asset_id == "src-1"


def test_learning_and_prompt_patterns_stay_on_platform(runtime):
    xhs = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="世界A", series="系列A")
    dy = _seed_account(runtime, platform="douyin", name="B", character="训练角色", world="世界B", series="系列B")
    runtime.store.save_prompt_pattern(PromptPattern(
        pattern_id="xhs-candid",
        platform="xiaohongshu",
        account_id=xhs.account_id,
        category="CANDID_SMARTPHONE_LIFESTYLE",
        prompt_fragment="candid smartphone lifestyle",
        positive_count=3,
    ))
    runtime.store.save_prompt_pattern(PromptPattern(
        pattern_id="global-light",
        platform="GLOBAL",
        category="LIGHT",
        prompt_fragment="natural daylight",
        global_pattern=True,
    ))
    xhs_patterns = runtime.store.list_prompt_patterns(platform="xiaohongshu", account_id=xhs.account_id)
    dy_patterns = runtime.store.list_prompt_patterns(platform="douyin", account_id=dy.account_id)
    assert any(item.pattern_id == "xhs-candid" for item in xhs_patterns)
    assert all(item.pattern_id != "xhs-candid" for item in dy_patterns)
    assert any(item.global_pattern for item in dy_patterns)


def test_list_assets_does_not_return_other_platform_primary(runtime, tmp_path):
    xhs = _seed_account(runtime, platform="xiaohongshu", name="A", character="张满血", world="世界A", series="系列A")
    dy = _seed_account(runtime, platform="douyin", name="B", character="训练角色", world="世界B", series="系列B")
    xhs_ep = runtime.continue_series(account_id=xhs.account_id, series_id=runtime.store.active_series(xhs.account_id).series_id, title="X1", brief="x")
    service = PlatformAssetService(runtime.store)
    service.import_asset(
        _png(tmp_path, "xhs.png", 50),
        account_id=xhs.account_id,
        platform="xiaohongshu",
        episode_id=xhs_ep.episode_id,
        asset_role="GENERATED_PRIMARY",
        no_prompt_reference=True,
        root=tmp_path / "assets",
    )
    dy_assets = service.list_assets(dy.account_id, "douyin", role="GENERATED_PRIMARY", include_global=False)
    assert dy_assets == []
