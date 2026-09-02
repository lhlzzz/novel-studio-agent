from creative.workflow.registry import get_workflow_version, list_workflows, register_workflow, resolve_workflow


def test_registry_lists_required_templates():
    names = {item.workflow_id for item in list_workflows()}
    for item in (
        "creator-video-default-v1",
        "creator-lifestyle-v1",
        "creator-image-to-video-v1",
        "character-consistency-v1",
        "scene-storyboard-v1",
        "short-drama-v1",
        "ugc-style-video-v1",
        "cinematic-video-v1",
        "product-optional-content-v1",
    ):
        assert item in names


def test_register_and_version_lookup():
    base = resolve_workflow("creator-lifestyle-v1")
    clone = register_workflow(type(base)(**{**base.__dict__, "version": "1.0.1"}))
    assert get_workflow_version("creator-lifestyle-v1", "1.0.1").version == "1.0.1"
    assert clone.workflow_id == "creator-lifestyle-v1"


def test_v442_workflow_aliases():
    for alias, target in {
        "creator-video-v1": "creator-video-default-v1",
        "image-to-video-v1": "creator-image-to-video-v1",
        "lifestyle-short-video-v1": "creator-lifestyle-v1",
    }.items():
        assert resolve_workflow(alias).workflow_id == target
