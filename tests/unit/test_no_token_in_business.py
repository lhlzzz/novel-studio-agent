from integrations.contracts.distribution import ContentVariant, DistributionJob, Publication
from content.models import ContentPackage
from social.handoff.models import XHSHandoff


FORBIDDEN = ("access_token", "refresh_token", "client_secret", "cookie", "session")


def test_no_token_in_business_models():
    package = ContentPackage("pkg", "t", "b")
    job = DistributionJob("j", "pkg", "a", ContentVariant("a", "hello"), provider="douyin", platform="douyin")
    publication = Publication("j", "a", "douyin", "post-1", platform="douyin")
    handoff = XHSHandoff(handoff_id="h", account_id="a", content_package_id="pkg")
    for item in (package, job, publication, handoff):
        dumped = str(item)
        for token in FORBIDDEN:
            assert token not in dumped


def test_no_token_in_distribution_job():
    job = DistributionJob("j", "pkg", "a", ContentVariant("a", "hello"), provider="douyin", platform="douyin")
    dumped = str(job.__dict__) if hasattr(job, "__dict__") else str(job)
    for token in FORBIDDEN:
        assert token not in dumped


def test_no_token_in_publication():
    publication = Publication("j", "a", "douyin", "post-1", platform="douyin")
    dumped = str(publication)
    for token in FORBIDDEN:
        assert token not in dumped


def test_no_token_in_logs():
    from governance.observability import log_event
    logged = log_event(agent="distribution-agent", action="publish", status="ok", access_token="leak", refresh_token="leak2", authorization="Bearer leak")
    text = str(logged)
    assert "leak" not in text
    assert "Bearer" not in text or logged.get("authorization") == "[redacted]"
