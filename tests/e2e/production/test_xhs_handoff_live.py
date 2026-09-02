from social.handoff.models import XHSHandoff


def test_xhs_live_direct_publish_blocked_handoff_ready():
    item = XHSHandoff(handoff_id="xhs-handoff-job", account_id="xiaohongshu:meiti", content_package_id="pkg")
    assert item.status == "READY_FOR_XHS"
    from social.providers.xiaohongshu.contract import DIRECT_PUBLISH_AVAILABLE, HANDOFF_ONLY
    assert HANDOFF_ONLY is True
    assert DIRECT_PUBLISH_AVAILABLE is False
