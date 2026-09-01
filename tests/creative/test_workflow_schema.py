from creative.schemas import NODE_TYPES, CreativeWorkflow, WorkflowEdge, WorkflowNode
from creative.workflow.registry import resolve_workflow, workflow_from_dict


def test_workflow_schema_rejects_unknown_node_type():
    try:
        workflow_from_dict({
            "workflow_id": "x",
            "version": "1.0.0",
            "nodes": [{"node_id": "a", "type": "not_a_node"}],
            "edges": [],
        })
    except ValueError as exc:
        assert "unknown node type" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_exported_workflow_has_no_top_level_provider():
    workflow = resolve_workflow("creator-image-to-video-v1")
    payload = workflow.export()
    assert "provider" not in payload
    assert any(node.provider == "lechuang" for node in workflow.nodes)
    assert set(NODE_TYPES)
    assert isinstance(workflow, CreativeWorkflow)
    assert all(isinstance(edge, WorkflowEdge) for edge in workflow.edges)
    assert all(isinstance(node, WorkflowNode) for node in workflow.nodes)
