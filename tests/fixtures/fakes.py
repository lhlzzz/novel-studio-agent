from integrations.contracts.distribution import (
    ContentVariant,
    DistributionJob,
    Integration,
    IntegrationCapabilities,
    MediaUploadResult,
    ProviderHealth,
)


class FakeAdapter:
    def __init__(self):
        self.integration = Integration(
            "i",
            "x",
            "account",
            "global",
            IntegrationCapabilities(publish=True, schedule=True, analytics=True, media_upload=True),
            "postiz",
            "postiz",
            True,
            state="ENABLED",
        )
        self.published = False

    def authenticate(self):
        return True

    def health(self):
        return ProviderHealth(provider="postiz", reachable=True, authenticated=True, account_count=1)

    def get_integration(self, integration_id):
        return self.integration

    def list_integrations(self):
        return [self.integration]

    def get_capabilities(self, integration_id):
        return self.integration.capabilities

    def get_settings(self, integration_id):
        return {"rules": []}

    def validate_payload(self, job):
        return []

    def upload_media(self, source_path: str) -> MediaUploadResult:
        return MediaUploadResult(
            source_hash="abc",
            source_path=source_path,
            mime_type="image/png",
            size=1,
            provider="postiz",
            remote_id="media-1",
            remote_path="https://postiz.test/m.png",
            uploaded_at="now",
        )

    def publish(self, job):
        self.published = True
        return {
            "id": "postiz-post-1",
            "externalId": "x-status-1",
            "status": "queued",
        }

    def schedule(self, job):
        return self.publish(job)

    def get_status(self, provider_post_id):
        return {"id": provider_post_id, "status": "published"}

    def cancel(self, provider_post_id):
        return {"id": provider_post_id, "deleted": True}

    def get_analytics(self, provider_post_id):
        return {"views": 4, "likes": 2}


class FakePostizClient:
    def __init__(self):
        self.created = None

    def is_connected(self):
        return True

    def health(self):
        return ProviderHealth(provider="postiz", reachable=True, authenticated=True, account_count=1)

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
        return {"id": "media-1", "path": "https://postiz.test/media.png"}

    def trigger_integration_tool(self, integration_id, method_name, data=None):
        return {"integration_id": integration_id, "tool": method_name}


def job() -> DistributionJob:
    return DistributionJob("job-1", "test-package-001", "i", ContentVariant("i", "test"))
