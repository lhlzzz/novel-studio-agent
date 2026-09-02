from social.providers.resolver import resolve_social_provider
from social.providers.xiaohongshu.adapter import XiaohongshuAdapter
from social.providers.errors import CapabilityUnsupported
from integrations.contracts.distribution import ContentVariant, DistributionJob
from pathlib import Path
import pytest


def test_resolver_returns_cn_adapters():
    assert resolve_social_provider("douyin").implementation.__class__.__name__ == "DouyinAdapter"
    assert resolve_social_provider("kuaishou").implementation.__class__.__name__ == "KuaishouAdapter"
    assert resolve_social_provider("xianyu").implementation.__class__.__name__ == "XianyuAdapter"
    assert resolve_social_provider("xiaohongshu").implementation.__class__.__name__ == "XiaohongshuAdapter"


def test_xhs_handoff_not_direct_publish(tmp_path):
    adapter = XiaohongshuAdapter()
    adapter.authenticate({"username": "meiti", "account_id": "xiaohongshu:meiti"})
    image = tmp_path / "a.jpg"
    image.write_bytes(b"jpeg")
    job = DistributionJob(
        "j", "p", "xiaohongshu:meiti",
        ContentVariant("xiaohongshu:meiti", "hello", media=(str(image),), title="hi", metadata={"approval": "approved"}),
        idempotency_key="k",
    )
    result = adapter.publish(job)
    assert result["status"] == "READY_FOR_XHS"
    assert result["handoff_id"]
    with pytest.raises(CapabilityUnsupported):
        adapter.publish_direct(job)
    status = adapter.get_status(result["id"])
    assert status["status"] == "NOT_PUBLISHED"


def test_xianyu_blocks_without_jushita(monkeypatch):
    monkeypatch.delenv("MEITI_XIANYU_DEPLOYMENT_MODE", raising=False)
    from social.providers.xianyu.adapter import XianyuAdapter
    adapter = XianyuAdapter()
    assert adapter.jushita_ready() is False
    with pytest.raises(Exception):
        adapter.publish(DistributionJob("j", "p", "a", ContentVariant("a", "x"), idempotency_key="k"))
