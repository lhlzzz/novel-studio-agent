def test_budget_blocks_before_generation(engine):
    run = engine.execute("creator-image-to-video-v1", {"brief": "too expensive", "variant_count": 4, "budget": 1})
    assert run.status == "BLOCKED"
    assert "budget" in (run.error or "").lower() or "exceeds" in (run.error or "")
    assert run.asset_ids == []
