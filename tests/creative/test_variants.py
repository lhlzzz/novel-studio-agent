def test_variants_are_ranked_and_all_kept(engine):
    run = engine.execute("creator-image-to-video-v1", {"brief": "four looks", "variant_count": 4, "budget": 80})
    assert run.status == "SUCCEEDED", run.error
    images = [engine.store.assets.get(item) for item in run.asset_ids if engine.store.assets.get(item).type == "image"]
    assert len(images) >= 4
    assert run.judge_results
    assert all("score" in item for item in run.judge_results)
