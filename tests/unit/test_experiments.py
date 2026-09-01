from analytics.experiments.models import create_experiment


def test_experiment_kinds_are_explicit():
    exp = create_experiment("hook", control={"text": "A"}, challenger={"text": "B"})
    assert exp.metric == "views"
    assert exp.control.kind == "hook"
    assert exp.variants[0].variant_id == "challenger"


def test_creative_experiment_kinds():
    exp = create_experiment("workflow", control={"workflow_id": "a"}, challenger={"workflow_id": "b"})
    assert exp.control.kind == "workflow"
    camera = create_experiment("camera", control={"movement": "static"}, challenger={"movement": "handheld"})
    assert camera.control.kind == "camera"
