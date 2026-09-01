def test_same_inputs_do_not_generate_twice(engine):
    inputs = {"brief": "idempotent lifestyle", "variant_count": 1, "budget": 40}
    first = engine.execute("creator-lifestyle-v1", inputs)
    second = engine.execute("creator-lifestyle-v1", inputs)
    assert first.run_id == second.run_id
    replay = engine.replay(first.run_id)
    assert replay.run_id != first.run_id
    assert replay.replay_of == first.run_id
    assert replay.status == "SUCCEEDED", replay.error
