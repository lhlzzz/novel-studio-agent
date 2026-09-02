import os

from scripts.social_doctor import evaluate_production_readiness, run


def live_status(provider: str) -> str:
    if os.getenv("MEITI_PRODUCTION_E2E") == "true":
        checks = run()
        report = {name.lower(): checks[name] for name in ("Xiaohongshu", "Douyin", "Kuaishou", "Xianyu")}
        item = report.get(provider) or {}
        e2e = item.get("Real E2E") or item.get("status") or "BLOCKED_EXTERNAL"
        if e2e == "LIVE_VERIFIED":
            return "LIVE_VERIFIED"
    return "BLOCKED_EXTERNAL"


def test_douyin_live_is_blocked_without_credentials():
    assert live_status("douyin") == "BLOCKED_EXTERNAL"
