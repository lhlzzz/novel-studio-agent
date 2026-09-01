def test_video_generation_is_image_to_video(engine):
    run = engine.execute("creator-image-to-video-v1", {"brief": "motion from still", "variant_count": 1, "budget": 40})
    videos = [engine.store.assets.get(item) for item in run.asset_ids if engine.store.assets.get(item).type in {"video", "final"}]
    assert videos
    video = next(item for item in videos if item.type == "video")
    assert video.duration == 15
    assert (video.metadata or {}).get("mode") == "image_to_video"
