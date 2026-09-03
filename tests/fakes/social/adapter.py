from dataclasses import replace

from integrations.contracts.distribution import (
    ContentVariant,
    DistributionJob,
    MediaUploadResult,
    ProviderHealth,
)
from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.auth.credentials import CredentialRecord


def _caps(**flags):
    claimed = {
        "text": True,
        "image": True,
        "video": False,
        "carousel": False,
        "story": False,
        "reel": False,
        "thread": True,
        "publish": True,
        "schedule": True,
        "analytics": True,
        "media_upload": True,
    }
    claimed.update(flags)
    return SocialProviderCapabilities.from_claimed(claimed, verified=True, method="runtime_test")


class _MemSecrets:
    def __init__(self):
        self.data = {}

    def put(self, payload, ref=None):
        record = payload if hasattr(payload, "to_payload") else CredentialRecord.from_payload(payload, ref=ref or "secret:fake")
        ref = ref or record.credential_ref or "secret:fake"
        self.data[ref] = record
        return ref

    def get(self, ref):
        record = self.data.get(ref)
        return record.to_payload() if record is not None else {}

    def get_record(self, ref):
        return self.data.get(ref)

    def delete(self, ref):
        self.data.pop(ref, None)

    def exists(self, ref):
        return ref in self.data


class FakeAdapter:
    provider = "x"

    def __init__(self):
        self.secrets = _MemSecrets()
        ref = self.secrets.put({"access_token": "fake-token", "provider": "x", "provider_account_id": "acct"})
        self.account = SocialAccount(
            account_id="i",
            provider="x",
            platform="x",
            username="meiti",
            display_name="Meiti",
            status="ENABLED",
            capabilities=_caps(),
            last_verified_at="now",
            credential_ref=ref,
            provider_account_id="acct",
        )
        self.published = False
        self.posts = {}

    @property
    def integration(self):
        return self.account.as_integration()

    def authenticate(self, authorization=None):
        return True

    def health(self):
        return ProviderHealth(provider="x", reachable=True, authenticated=True, account_count=1)

    def get_account(self, account_id):
        if account_id != self.account.account_id:
            raise KeyError(account_id)
        return self.account

    def bind_account(self, account):
        self.account = account
        return account

    def get_integration(self, integration_id):
        return self.get_account(integration_id).as_integration()

    def list_accounts(self):
        return [self.account]

    def list_integrations(self):
        return [self.account.as_integration()]

    def get_capabilities(self, integration_id):
        return self.account.capabilities.to_integration()

    def capabilities(self, account_id):
        return self.account.capabilities

    def verify_capabilities(self, account_id):
        return self.account.capabilities

    def get_settings(self, integration_id):
        return {"rules": [], "platform": "x"}

    def validate_payload(self, job):
        return []

    def upload_media(self, source_path: str, *, account_id: str = "", idempotency_key: str = "") -> MediaUploadResult:
        return MediaUploadResult(
            source_hash="abc",
            source_path=source_path,
            mime_type="image/png",
            size=1,
            provider="x",
            remote_id="media-1",
            remote_path="https://api.x.com/media/1",
            uploaded_at="now",
        )

    def ensure_media(self, job):
        uploaded = [self.upload_media(path) for path in job.variant.media]
        return replace(job, media_uploads=tuple(uploaded)), uploaded

    def publish(self, job):
        self.published = True
        result = {
            "id": "x-post-1",
            "provider_object_id": "x-post-1",
            "provider_request_id": "x-req-1",
            "externalId": "x-status-1",
            "status": "queued",
            "url": "https://x.com/i/web/status/x-post-1",
        }
        self.posts[result["id"]] = result
        return result

    def schedule(self, job):
        return self.publish(job)

    def get_status(self, provider_post_id, *, account_id: str = "", provider_object_type: str = "publication"):
        return {"id": provider_post_id, "status": "published"}

    def cancel(self, provider_post_id, *, account_id: str = ""):
        return {"id": provider_post_id, "deleted": True}

    def delete(self, provider_post_id, *, account_id: str = ""):
        return self.cancel(provider_post_id, account_id=account_id)

    def get_analytics(self, provider_post_id, *, account_id: str = ""):
        return {"views": 4, "likes": 2, "comments": None, "shares": None, "followers_delta": None}

    def analytics(self, publication):
        return self.get_analytics(publication.provider_post_id)


def job() -> DistributionJob:
    return DistributionJob("job-1", "test-package-001", "i", ContentVariant("i", "test"), provider="x", platform="x", idempotency_key="k")
