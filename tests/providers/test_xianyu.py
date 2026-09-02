import pytest
from social.providers.xianyu.adapter import XianyuAdapter
from integrations.contracts.distribution import ContentVariant, DistributionJob
from social.providers.errors import CapabilityUnsupported, PolicyBlocked, ValidationError


def test_local_mode_blocks_listing(monkeypatch):
    monkeypatch.delenv("MEITI_XIANYU_DEPLOYMENT_MODE", raising=False)
    adapter = XianyuAdapter()
    assert adapter.jushita_ready() is False
    with pytest.raises(CapabilityUnsupported):
        adapter.publish(DistributionJob("j", "p", "a", ContentVariant("a", "x", metadata={"commerce_intent": "sell", "listing": {"title": "t", "price": "1", "category_id": "c"}}), idempotency_key="k"))


def test_requires_commerce_intent(monkeypatch):
    monkeypatch.setenv("MEITI_XIANYU_DEPLOYMENT_MODE", "JUSHITA")
    adapter = XianyuAdapter()
    with pytest.raises(PolicyBlocked):
        adapter.publish(DistributionJob("j", "p", "a", ContentVariant("a", "x", metadata={"commerce_intent": "none"}), idempotency_key="k"))


def test_local_identity_unverified(monkeypatch, tmp_path):
    from social.auth.secrets import RuntimeSecretStore
    from social.auth.credentials import CredentialRecord
    monkeypatch.delenv("MEITI_XIANYU_DEPLOYMENT_MODE", raising=False)
    adapter = XianyuAdapter()
    adapter.secrets = RuntimeSecretStore(tmp_path)
    adapter._credential_ref = adapter.secrets.put(CredentialRecord.from_payload({"provider": "xianyu", "access_token": "t", "provider_account_id": "uid-1"}))
    accounts = adapter._discover_accounts({"access_token": "t", "provider_account_id": "uid-1"})
    assert accounts[0].status == "IDENTITY_UNVERIFIED"
