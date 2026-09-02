#!/usr/bin/env python3
"""Social doctor: registry, accounts, OAuth availability, capabilities, API reachability."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _status(ok: bool, **extra) -> dict:
    payload = {"status": "PASS" if ok else "BLOCKED"}
    payload.update(extra)
    return payload


def check_provider_registry() -> dict:
    from social.providers.registry import NATIVE_PROVIDERS, load_social_registry

    registry = load_social_registry()
    missing = [name for name in NATIVE_PROVIDERS if name not in registry]
    enabled_from_yaml = [name for name, item in registry.items() if item.enabled]
    return _status(not missing and not enabled_from_yaml, providers=sorted(registry), missing=missing, enabled=enabled_from_yaml)


def check_account_manager() -> dict:
    from social.accounts.manager import SocialAccountManager

    manager = SocialAccountManager()
    accounts = manager.list_accounts()
    rows = manager.doctor_rows()
    return _status(True, account_count=len(accounts), accounts=rows)


def check_oauth_availability() -> dict:
    required = {
        "x": ("X_CLIENT_ID", "X_CLIENT_SECRET"),
        "instagram": ("INSTAGRAM_CLIENT_ID", "INSTAGRAM_CLIENT_SECRET"),
        "youtube": ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"),
        "tiktok": ("TIKTOK_CLIENT_ID", "TIKTOK_CLIENT_SECRET"),
        "linkedin": ("LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET"),
    }
    availability = {}
    for provider, envs in required.items():
        availability[provider] = all(os.getenv(name, "").strip() for name in envs)
    return {
        "status": "PASS" if any(availability.values()) else "BLOCKED",
        "oauth": availability,
        "reason": None if any(availability.values()) else "no native social OAuth credentials",
    }


def check_capabilities() -> dict:
    from social.providers.resolver import PROVIDER_CAPABILITIES

    bad = []
    for provider, caps in PROVIDER_CAPABILITIES.items():
        if all(item.get("api") for item in caps.values()):
            bad.append(provider)
    return _status(not bad, providers=sorted(PROVIDER_CAPABILITIES), all_true=bad)


def check_provider_health() -> dict:
    from social.providers.resolver import resolve_social_provider
    from social.providers.registry import NATIVE_PROVIDERS

    results = {}
    for name in NATIVE_PROVIDERS:
        handle = resolve_social_provider(name)
        health = handle.implementation.health()
        if health.authenticated and health.reachable:
            status = "PASS"
        elif health.reachable:
            status = "WARN"
        else:
            status = "BLOCKED"
        results[name] = {
            "status": status,
            "reachable": health.reachable,
            "authenticated": health.authenticated,
            "account_count": health.account_count,
            "reason": health.last_error,
        }
    overall = "PASS" if all(item["status"] == "PASS" for item in results.values()) else "BLOCKED"
    return {"status": overall, "providers": results}


def run() -> dict:
    return {
        "Social Provider Registry": check_provider_registry(),
        "Social Account Manager": check_account_manager(),
        "OAuth Availability": check_oauth_availability(),
        "Provider Capabilities": check_capabilities(),
        "Social Provider Health": check_provider_health(),
    }


def main() -> int:
    checks = run()
    for name, item in checks.items():
        print(f"{name}: {item.get('status')}")
        if name == "Social Account Manager":
            for row in item.get("accounts") or []:
                print(f"{row['label']}: {row['status']} ACTION: {row['action']}")
    blocked = [name for name, item in checks.items() if item.get("status") != "PASS"]
    print("Overall:", "READY" if not blocked else "BLOCKED")
    print(json.dumps({"ready": not blocked, "checks": {k: v.get("status") for k, v in checks.items()}, "details": checks}, default=str))
    return 0 if not blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
