from creative.workflow.resolver import resolve_from_requirement


def test_lifestyle_brief_selects_lifestyle_workflow():
    workflow = resolve_from_requirement({
        "brief": "15秒自然生活方式视频",
        "aspect_ratio": "9:16",
        "face_visible": False,
        "style": "natural lifestyle",
    })
    assert workflow.workflow_id == "creator-lifestyle-v1"


def test_drama_and_commerce_selection():
    assert resolve_from_requirement({"brief": "short drama script"}).workflow_id == "short-drama-v1"
    assert resolve_from_requirement({"brief": "ugc street interview"}).workflow_id == "ugc-style-video-v1"
    assert resolve_from_requirement({"brief": "cinematic night walk"}).workflow_id == "cinematic-video-v1"
    assert resolve_from_requirement({"brief": "story", "commerce_intent": "affiliate"}).workflow_id == "product-optional-content-v1"
