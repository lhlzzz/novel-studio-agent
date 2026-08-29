from integrations.adapters.unsupported import UnsupportedDistributionAdapter
from integrations.contracts.distribution import Integration, IntegrationCapabilities, UnsupportedCapabilityError


def test_unverified_adapter_is_explicitly_unsupported():
    integration = Integration("douyin", "douyin", "", "cn", IntegrationCapabilities(), "douyin", "custom")
    adapter = UnsupportedDistributionAdapter(integration)
    assert adapter.prepare_publish(None)["status"] == "unsupported"
    try:
        adapter.publish(None)
    except UnsupportedCapabilityError as exc:
        assert "unsupported" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unsupported adapter must fail closed")


def test_postiz_adapter_exposes_required_distribution_operations():
    from integrations.providers.postiz.adapter import PostizDistributionAdapter

    adapter = PostizDistributionAdapter(base_url="http://127.0.0.1:9")
    for operation in ("authenticate", "health", "list_integrations", "get_capabilities",
                      "upload_media", "publish", "schedule", "get_status", "cancel",
                      "get_analytics"):
        assert callable(getattr(adapter, operation))


class FakePostizClient:
    def __init__(self):
        self.created = None

    def is_connected(self):
        return True

    def list_integrations(self, group=None):
        return {"data": [{"id": "x-123", "identifier": "x", "name": "test"}]}

    def get_integration_settings(self, integration_id):
        return {"rules": []}

    def create_post(self, payload):
        self.created = payload
        return [{"postId": "postiz-post-1", "integration": "x-123"}]

    def list_posts(self, **kwargs):
        return {"data": [{"id": "postiz-post-1", "status": "published"}]}

    def delete_post(self, post_id):
        return {"id": post_id, "deleted": True}

    def get_post_analytics(self, post_id, days=7):
        return {"views": 4, "likes": 2}

    def get_integration_analytics(self, integration_id, days=30):
        return {"views": 4}

    def upload_media(self, file_path):
        return {"path": "https://postiz.test/media.png"}

    def trigger_integration_tool(self, integration_id, method_name, data=None):
        return {"integration_id": integration_id, "tool": method_name}


def test_postiz_adapter_maps_contract_to_single_client():
    from integrations.contracts.distribution import ContentVariant, DistributionJob
    from integrations.providers.postiz.adapter import PostizAdapter

    client = FakePostizClient()
    adapter = PostizAdapter(client=client)
    job = DistributionJob("job-1", "pkg-1", "x-123", ContentVariant("x-123", "hello"))
    adapter.verify_capabilities("x-123")

    assert adapter.get_integration("x-123").capabilities.media_upload is True
    assert adapter.validate_payload(job) == []
    result = adapter.publish(job)

    assert result["id"] == "postiz-post-1"
    assert client.created["posts"][0]["integration"] == {"id": "x-123"}
    assert client.created["type"] == "now"
    assert client.created["posts"][0]["settings"]["__type"] == "x"
    assert client.created["date"]


def test_postiz_adapter_rejects_unknown_integration_without_network_side_effect():
    from integrations.providers.postiz.adapter import PostizAdapter
    from integrations.contracts.distribution import ContentVariant, DistributionJob

    adapter = PostizAdapter(client=FakePostizClient())
    job = DistributionJob("job-1", "pkg-1", "missing", ContentVariant("missing", "hello"))
    assert adapter.validate_payload(job) == ["unknown Postiz integration: missing"]
