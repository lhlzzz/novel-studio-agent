from dataclasses import replace

from integrations.contracts.distribution import (
    CapabilityRecord,
    Integration,
    IntegrationCapabilities,
    MediaUploadResult,
    ProviderHealth,
)


class FakePostizAdapter:
    provider = "postiz"

    def __init__(self):
        self.posts = {}
        self.analytics = {}
        self.published = []
        capabilities = IntegrationCapabilities(
            publish=True, schedule=True, analytics=True, media=True, media_upload=True,
            records={name: CapabilityRecord(name, True, True, method="runtime_test", verification_method="runtime_test") for name in ("publish", "schedule", "analytics", "media", "media_upload")},
        )
        self.integration = Integration(
            "x-test", "x", "acct", "global", capabilities, "postiz", "postiz", True, state="ENABLED"
        )

    def authenticate(self):
        return True

    def health(self):
        return ProviderHealth(provider=self.provider, reachable=True, authenticated=True, account_count=1)

    def list_integrations(self):
        return [self.integration]

    def get_integration(self, integration_id):
        if integration_id != self.integration.id:
            raise KeyError(integration_id)
        return self.integration

    def get_capabilities(self, integration_id):
        return self.get_integration(integration_id).capabilities

    def get_settings(self, integration_id):
        return {"__type": "x"}

    def validate_payload(self, job):
        return []

    def prepare_publish(self, job):
        return {"status": "prepared"}

    def upload_media(self, source_path: str) -> MediaUploadResult:
        return MediaUploadResult(
            source_hash="abc",
            source_path=source_path,
            mime_type="image/png",
            size=1,
            provider=self.provider,
            remote_id="media-1",
            remote_path="https://postiz.test/m.png",
            uploaded_at="now",
            status="uploaded",
        )

    def ensure_media(self, job):
        uploaded = [self.upload_media(path) for path in job.variant.media]
        return job, uploaded

    def publish(self, job):
        post_id = f"postiz-{job.job_id}"
        self.posts[post_id] = {"id": post_id, "status": "published", "externalId": f"x-{job.job_id}"}
        self.published.append(job.job_id)
        self.analytics[post_id] = {"views": 11, "likes": 2, "comments": None, "shares": None}
        return self.posts[post_id]

    def schedule(self, job):
        result = self.publish(job)
        result["status"] = "scheduled"
        return result

    def get_status(self, provider_post_id):
        return self.posts.get(provider_post_id, {"id": provider_post_id, "status": "UNKNOWN"})

    def get_analytics(self, provider_post_id):
        return self.analytics.get(provider_post_id, {})

    def cancel(self, provider_post_id):
        return {"id": provider_post_id, "deleted": True}

    def delete(self, provider_post_id):
        return self.cancel(provider_post_id)
