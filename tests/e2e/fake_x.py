from dataclasses import replace

from integrations.contracts.distribution import MediaUploadResult, ProviderHealth
from social.accounts.models import SocialAccount, SocialProviderCapabilities
from tests.fixtures.fakes import _MemSecrets


class FakeXAdapter:
    provider = "x"
    platform = "x"

    def __init__(self):
        self.posts = {}
        self.analytics_data = {}
        self.published = []
        self.secrets = _MemSecrets()
        self._credential_ref = self.secrets.put({"access_token": "fake-token", "provider": "x", "provider_account_id": "acct"})
        capabilities = SocialProviderCapabilities.from_claimed(
            {
                "text": True, "image": True, "video": True, "thread": True, "publish": True,
                "media_upload": True, "analytics": True, "schedule": False, "carousel": False,
                "story": False, "reel": False,
            },
            verified=True,
            method="runtime_test",
        )
        self.account = SocialAccount(
            account_id="x-test",
            provider="x",
            platform="x",
            username="meiti",
            display_name="Meiti",
            status="ENABLED",
            capabilities=capabilities,
            last_verified_at="now",
            provider_account_id="acct",
            credential_ref=self._credential_ref,
        )

    @property
    def integration(self):
        return self.account.as_integration()

    def authenticate(self, authorization=None):
        return True

    def health(self):
        return ProviderHealth(provider=self.provider, reachable=True, authenticated=True, account_count=1)

    def list_accounts(self):
        return [self.account]

    def list_integrations(self):
        return [self.account.as_integration()]

    def get_account(self, account_id):
        if account_id != self.account.account_id:
            raise KeyError(account_id)
        return self.account

    def get_integration(self, integration_id):
        return self.get_account(integration_id).as_integration()

    def get_capabilities(self, integration_id):
        return self.get_account(integration_id).capabilities.to_integration()

    def capabilities(self, account_id):
        return self.get_account(account_id).capabilities

    def verify_capabilities(self, account_id):
        self.account = self.get_account(account_id)
        verified = SocialProviderCapabilities.from_claimed(self.account.capabilities.claimed(), verified=True, method="runtime_test")
        self.account = replace(self.account, capabilities=verified)
        return verified

    def get_settings(self, integration_id):
        return {"platform": "x"}

    def validate_payload(self, job):
        return []

    def prepare_publish(self, job):
        return {"status": "prepared"}

    def upload_media(self, source_path: str, *, account_id: str = "", idempotency_key: str = "") -> MediaUploadResult:
        return MediaUploadResult(
            source_hash="abc",
            source_path=source_path,
            mime_type="image/png",
            size=1,
            provider=self.provider,
            remote_id="media-1",
            remote_path="https://api.x.com/media/1",
            uploaded_at="now",
            status="uploaded",
        )

    def ensure_media(self, job):
        uploaded = [self.upload_media(path) for path in job.variant.media]
        return job, uploaded

    def publish(self, job):
        post_id = f"x-{job.job_id}"
        self.posts[post_id] = {"id": post_id, "status": "published", "externalId": f"xobj-{job.job_id}", "url": f"https://x.com/i/web/status/{post_id}"}
        self.published.append(job.job_id)
        self.analytics_data[post_id] = {"views": 11, "likes": 2, "comments": None, "shares": None, "followers_delta": None}
        return self.posts[post_id]

    def schedule(self, job):
        result = dict(self.publish(job))
        result["status"] = "scheduled"
        self.posts[result["id"]] = result
        return result

    def get_status(self, provider_post_id, *, provider_object_type: str = "publication"):
        return self.posts.get(provider_post_id, {"id": provider_post_id, "status": "UNKNOWN"})

    def get_analytics(self, provider_post_id):
        return self.analytics_data.get(provider_post_id, {"views": None, "likes": None, "comments": None, "shares": None, "followers_delta": None})

    def analytics(self, publication):
        return self.get_analytics(publication.provider_post_id)

    def cancel(self, provider_post_id):
        return {"id": provider_post_id, "deleted": True}

    def delete(self, provider_post_id):
        return self.cancel(provider_post_id)
