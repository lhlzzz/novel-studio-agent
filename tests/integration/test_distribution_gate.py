from integrations.contracts.distribution import ContentVariant, DistributionJob
from governance.distribution_gate import check_distribution_job
from tests.fixtures.fakes import FakeAdapter


def _job(**meta):
    metadata = {"approval": meta.pop("approval", None)}
    metadata = {k: v for k, v in metadata.items() if v is not None}
    return DistributionJob("j", "p", "i", ContentVariant("i", "test", metadata=metadata), idempotency_key="k")


def test_distribution_gate_blocks_missing_approval():
    adapter = FakeAdapter()
    failures = check_distribution_job(_job(), adapter.account, adapter=adapter)
    assert "approval invalid" in failures


def test_unverified_capability_blocks():
    adapter = FakeAdapter()
    from social.accounts.models import SocialProviderCapabilities
    from dataclasses import replace
    adapter.account = replace(adapter.account, capabilities=SocialProviderCapabilities.from_claimed({"publish": True, "text": True}, verified=False))
    failures = check_distribution_job(_job(approval="approved"), adapter.account, adapter=adapter, store=None)
    assert "capability unverified" in failures
