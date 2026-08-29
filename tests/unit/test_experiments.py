from analytics.experiments.models import create_experiment


def test_experiment_kinds_are_explicit():
    exp = create_experiment("hook", control={"text": "A"}, challenger={"text": "B"})
    assert exp.metric == "views"
    assert exp.control.kind == "hook"
    assert exp.variants[0].variant_id == "challenger"
