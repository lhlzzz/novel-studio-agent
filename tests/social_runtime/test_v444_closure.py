from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from commerce.models import CommerceDecision
from commerce.xianyu import XianyuListing
from content.models import ContentPackage
from integrations.contracts.distribution import ContentVariant, DistributionJob, PublicationOutcome
from integrations.distribution_service import DistributionService, ExternalActionBlocked
from integrations.persistence import InMemoryStore
from social.accounts.models import SocialAccount, SocialProviderCapabilities, enable_account, transition_account
from social.auth.credentials import CredentialRecord
from social.handoff.models import transition_handoff
from social.providers.errors import CapabilityUnsupported, PolicyBlocked, TokenExpired
from social.providers.xiaohongshu.adapter import XiaohongshuAdapter
from social.providers.xianyu.adapter import XianyuAdapter
from social.runtime.container import SocialRuntime
from tests.fakes.social.adapter import FakeAdapter


def _xhs_job(tmp_path, job_id="j"):
    path = tmp_path / "img.jpg"
    path.write_bytes(b"jpeg")
    return DistributionJob(
        job_id,
        "pkg",
        "xiaohongshu:meiti",
        ContentVariant("xiaohongshu:meiti", "hello", media=(str(path),), title="hi", metadata={"approval": "approved"}),
        idempotency_key=f"k-{job_id}",
        provider="xiaohongshu",
        platform="xiaohongshu",
        request_id=f"req-{job_id}",
    )


def test_same_job_never_creates_two_handoffs(tmp_path):
    adapter = XiaohongshuAdapter()
    adapter.authenticate({"username": "meiti", "account_id": "xiaohongshu:meiti"})
    store = InMemoryStore()
    service = DistributionService(adapter, store=store)
    job = _xhs_job(tmp_path)
    first = service.execute(job, gate_check=lambda item: True)
    second = service.execute(job, gate_check=lambda item: True)
    assert first.handoff_id == second.handoff_id == "xhs-handoff-j"
    assert len([key for key in store.handoffs if not str(key).startswith("job:")]) == 1


def test_handoff_transitions_persist(tmp_path):
    adapter = XiaohongshuAdapter()
    adapter.authenticate({"username": "meiti", "account_id": "xiaohongshu:meiti"})
    store = InMemoryStore()
    result = DistributionService(adapter, store=store).execute(_xhs_job(tmp_path), gate_check=lambda item: True)
    opened = transition_handoff(result.handoff, "OPENED")
    store.save_handoff(opened)
    loaded = store.get_handoff_by_job("j")
    assert loaded.status == "OPENED"
    ready = transition_handoff(loaded, "READY_FOR_XHS")
    store.save_handoff(ready)
    assert store.get_handoff_by_job("j").status == "READY_FOR_XHS"


def test_xianyu_media_capability_not_verified_without_bytes_contract(monkeypatch, tmp_path):
    from social.auth.secrets import RuntimeSecretStore
    monkeypatch.setenv("MEITI_XIANYU_DEPLOYMENT_MODE", "JUSHITA")
    adapter = XianyuAdapter()
    adapter.secrets = RuntimeSecretStore(tmp_path)
    adapter._credential_ref = adapter.secrets.put(CredentialRecord.from_payload({"provider": "xianyu", "access_token": "t", "provider_account_id": "uid"}))
    account = SocialAccount("xianyu:uid", "xianyu", "xianyu", username="meiti", status="AUTHENTICATED", provider_account_id="uid", credential_ref=adapter._credential_ref)
    adapter._accounts[account.account_id] = account
    caps = adapter.verify_capabilities(account.account_id)
    assert caps.records["media_upload"].supported is False
    assert caps.records["media_upload"].live_verified is False
    assert caps.records["media_upload"].contract_verified is False
    with pytest.raises(CapabilityUnsupported):
        adapter._upload_bytes(b"abc", mime_type="image/jpeg", filename="a.jpg", account_id=account.account_id, idempotency_key="k")


def test_xianyu_listing_persisted_once_by_service_not_adapter(monkeypatch, tmp_path):
    monkeypatch.setenv("MEITI_XIANYU_DEPLOYMENT_MODE", "JUSHITA")
    adapter = XianyuAdapter()
    adapter.secrets = __import__("social.auth.secrets", fromlist=["RuntimeSecretStore"]).RuntimeSecretStore(tmp_path)
    adapter._credential_ref = adapter.secrets.put(CredentialRecord.from_payload({"provider": "xianyu", "access_token": "t", "provider_account_id": "uid"}))
    account = SocialAccount(
        "xianyu:uid", "xianyu", "xianyu", username="meiti", status="ENABLED",
        provider_account_id="uid", credential_ref=adapter._credential_ref,
        capabilities=SocialProviderCapabilities.from_claimed({"listing": True, "image": True}, verified=True, method="test"),
    )
    adapter._accounts[account.account_id] = account
    adapter.xy_client.item_publish = lambda *args, **kwargs: {"item_id": "item-1", "request_id": "xy-req"}
    store = InMemoryStore()
    store.save_account(account)
    job = DistributionJob(
        "job-xy", "pkg", "xianyu:uid",
        ContentVariant("xianyu:uid", "desc", metadata={
            "approval": "approved",
            "commerce_intent": "sell",
            "listing": {"title": "bike", "price": "12.5", "category_id": "cat", "quantity": 1},
            "uploaded_media": [{"remote_id": "media-9"}],
        }),
        idempotency_key="xy-k", provider="xianyu", platform="xianyu", request_id="req-xy",
    )
    result = DistributionService(adapter, store=store).execute(job, gate_check=lambda item: True)
    assert result.kind == "listing"
    assert store.get_listing_by_job("job-xy").provider_item_id == "item-1"
    assert store.get_publication("job-xy") is None
    again = DistributionService(adapter, store=store).execute(job, gate_check=lambda item: True)
    assert again.listing.listing_id == result.listing.listing_id


def test_refresh_is_account_scoped():
    runtime = SocialRuntime.testing()
    caps = SocialProviderCapabilities.from_claimed({"publish": True, "video": True}, verified=True, method="test")

    class Auth:
        def __init__(self, token):
            self.token = token
            self.seen = []
        def refresh(self, refresh_token):
            self.seen.append(refresh_token)
            return CredentialRecord.from_payload({"provider": "douyin", "access_token": self.token, "refresh_token": refresh_token, "provider_account_id": refresh_token})

    class Adapter:
        provider = "douyin"
        def __init__(self, account, auth):
            self.account = account
            self.auth = auth
            self._accounts = {account.account_id: account}
        def get_account(self, account_id):
            return self.account
        def verify_capabilities(self, account_id):
            return self.account.capabilities
        def list_accounts(self):
            return [self.account]

    accounts = []
    adapters = []
    for name, token in (("a", "new-a"), ("b", "new-b")):
        account = runtime.manager.save(SocialAccount(f"douyin:{name}", "douyin", "douyin", username=name, status="AUTHENTICATED", capabilities=caps, provider_account_id=name))
        account = runtime.manager.save(transition_account(account, "VERIFYING"))
        account = runtime.manager.save(transition_account(account, "VERIFIED", capabilities=caps))
        account = runtime.manager.save(enable_account(account))
        ref = runtime.secrets.put(CredentialRecord.from_payload({"provider": "douyin", "access_token": f"old-{name}", "refresh_token": f"rt-{name}", "provider_account_id": name}))
        account = runtime.manager.save(replace(account, credential_ref=ref))
        auth = Auth(token)
        adapter = Adapter(account, auth)
        accounts.append((account, ref, auth))
        adapters.append(adapter)
        runtime.manager.refresh_account(account.account_id, adapter=adapter)
    assert runtime.secrets.get_record(accounts[0][1]).access_token == "new-a"
    assert runtime.secrets.get_record(accounts[1][1]).access_token == "new-b"
    assert accounts[0][2].seen == ["rt-a"]
    assert accounts[1][2].seen == ["rt-b"]


def test_credentials_read_does_not_refresh(tmp_path):
    from social.auth.secrets import RuntimeSecretStore
    from social.providers.base import BaseCNAdapter
    class Probe(BaseCNAdapter):
        provider = "douyin"
        def refresh(self, account):
            raise AssertionError("refresh must not run from _credentials")
    adapter = Probe(secrets=RuntimeSecretStore(tmp_path))
    expired = datetime.now(timezone.utc) - timedelta(hours=1)
    ref = adapter.secrets.put(CredentialRecord.from_payload({"provider": "douyin", "access_token": "old", "refresh_token": "rt", "expires_at": expired.isoformat()}))
    account = SocialAccount("douyin:x", "douyin", "douyin", credential_ref=ref, provider_account_id="x", status="ENABLED")
    with pytest.raises(TokenExpired):
        adapter._credentials(account)


def test_missing_provider_is_blocked():
    adapter = FakeAdapter()
    store = InMemoryStore()
    job = DistributionJob("j", "p", "i", ContentVariant("i", "hello", metadata={"approval": "approved"}), idempotency_key="k")
    with pytest.raises(ExternalActionBlocked, match="provider and platform are required"):
        DistributionService(adapter, store=store).execute(job, gate_check=lambda item: True)


def test_provider_not_guessed_from_variant_metadata():
    adapter = FakeAdapter()
    store = InMemoryStore()
    job = DistributionJob(
        "j", "p", "i",
        ContentVariant("i", "hello", metadata={"approval": "approved", "platform": "douyin"}),
        idempotency_key="k",
    )
    with pytest.raises(ExternalActionBlocked, match="provider and platform are required"):
        DistributionService(adapter, store=store).execute(job, gate_check=lambda item: True)


def test_http_200_is_not_published():
    adapter = FakeAdapter()
    store = InMemoryStore()
    outcome = DistributionService(adapter, store=store).execute(
        DistributionJob("job-1", "pkg", "i", ContentVariant("i", "hello", metadata={"approval": "approved"}), idempotency_key="k", provider="x", platform="x"),
        gate_check=lambda item: True,
    )
    assert isinstance(outcome, PublicationOutcome)
    assert outcome.publication.status != "PUBLISHED"
    assert outcome.provider_object_id == "x-post-1"
    assert outcome.provider_request_id == "x-req-1"
    assert outcome.request_id != outcome.provider_object_id


def test_content_cannot_implicitly_create_listing():
    package = ContentPackage("pkg", "Title", "Body", commerce_intent="none")
    assert CommerceDecision(intent=package.commerce_intent).allows_listing() is False
    from social.variants import build_platform_variant
    with pytest.raises(ValueError):
        build_platform_variant(package, account_id="xianyu:1", platform="xianyu")


def test_xianyu_listing_validates_price_quantity_category():
    with pytest.raises(ValueError):
        XianyuListing(listing_id="l", account_id="a", title="t", description="d", price="0", category_id="c")
    with pytest.raises(ValueError):
        XianyuListing(listing_id="l", account_id="a", title="t", description="d", price="1", quantity=0, category_id="c")
    with pytest.raises(ValueError):
        XianyuListing(listing_id="l", account_id="a", title="t", description="d", price="1", category_id="")
