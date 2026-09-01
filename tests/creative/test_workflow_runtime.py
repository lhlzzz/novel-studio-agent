from creative.workflow.engine import CreativeWorkflowEngine


def test_mock_workflow_runtime_succeeds(engine: CreativeWorkflowEngine):
    run = engine.execute(
        "creator-image-to-video-v1",
        {"brief": "young woman lifestyle, no hard sell", "aspect_ratio": "9:16", "duration_seconds": 15, "variant_count": 2, "budget": 40, "face_visible": False},
    )
    assert run.status == "SUCCEEDED", run.error
    assert run.workflow_snapshot["workflow_id"] == "creator-image-to-video-v1"
    assert run.asset_ids
    assert run.actual_cost > 0
    package = engine.to_content_package(run, title="Lifestyle")
    assert package.media_assets
    assert "lechuang" not in (package.metadata or {})
    assert package.metadata["creative_run_id"] == run.run_id
