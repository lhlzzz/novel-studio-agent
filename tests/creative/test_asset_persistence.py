from creative.assets import MIN_PNG, AssetStore, Character


def test_assets_are_immutable_and_characters_are_reusable(tmp_path):
    store = AssetStore(root=tmp_path)
    asset = store.save_generated(MIN_PNG, asset_type="image", suffix=".png", mime_type="image/png", width=1, height=1)
    duplicate = store.save_generated(MIN_PNG, asset_type="image", suffix=".png", mime_type="image/png", width=1, height=1)
    assert duplicate.asset_id == asset.asset_id
    character = store.put_character(Character(character_id="c1", name="Ava", reference_assets=(asset.asset_id,)))
    assert store.get_character("c1").reference_assets == (asset.asset_id,)
    assert character.name == "Ava"
