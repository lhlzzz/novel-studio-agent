from integrations.adapters.postiz.adapter import PostizDistributionAdapter
from integrations.providers.postiz.client import PostizClient


def test_postiz_connection_is_configurable_without_hardcoded_credentials():
    adapter = PostizDistributionAdapter(base_url="http://127.0.0.1:4007")
    assert adapter.base_url == "http://127.0.0.1:4007"
    assert adapter.api_key == ""


def test_postiz_client_owns_runtime_configuration():
    client = PostizClient(base_url="http://postiz.test/", api_key="secret")
    assert client.base_url == "http://postiz.test"
    assert client.api_key == "secret"
