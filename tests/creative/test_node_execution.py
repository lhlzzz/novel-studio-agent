from creative.nodes import estimate_workflow_cost
from creative.workflow.registry import resolve_workflow


def test_cost_scales_with_variants():
    workflow = resolve_workflow("creator-image-to-video-v1")
    one = estimate_workflow_cost(workflow, {"variant_count": 1})
    four = estimate_workflow_cost(workflow, {"variant_count": 4})
    assert four > one


def test_prompt_and_character_nodes_run(engine):
    from creative.assets import Character
    engine.store.assets.put_character(Character(character_id="char-1", name="Ava"))
    run = engine.execute(
        "character-consistency-v1",
        {"brief": "same wardrobe across shots", "character_id": "char-1", "variant_count": 1, "budget": 40},
    )
    assert run.status == "SUCCEEDED", run.error
    assert run.node_outputs["character"]["character_id"] == "char-1"
    assert "prompt" in run.node_outputs["scene"] or "output" in run.node_outputs["scene"]
