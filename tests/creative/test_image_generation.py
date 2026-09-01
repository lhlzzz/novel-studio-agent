def test_image_generation_writes_hashed_asset(engine):
    run = engine.execute("creator-image-to-video-v1", {"brief": "still frame", "variant_count": 1, "budget": 40})
    images = [engine.store.assets.get(item) for item in run.asset_ids if engine.store.assets.get(item).type in {"image", "final"}]
    assert images
    image = next(item for item in images if item.type == "image")
    assert image.sha256
    assert image.width == 720
    assert image.height == 1280
    assert image.path.endswith(image.sha256 + ".png") or image.sha256 in image.path
