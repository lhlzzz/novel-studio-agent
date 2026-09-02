import os

from scripts.social_doctor import evaluate_production_readiness, run


def test_missing_credentials_are_blocked_external_not_skipped():
    assert os.getenv("MEITI_PRODUCTION_E2E", "false") in {"false", "true", ""}
    checks = run()
    readiness = evaluate_production_readiness(checks)
    assert readiness["architecture"] in {"PASS", "FAIL"}
    if os.getenv("MEITI_PRODUCTION_E2E") != "true":
        assert readiness["overall"] == "BLOCKED_EXTERNAL"
        assert readiness["external_ready"] is False
