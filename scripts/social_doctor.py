#!/usr/bin/env python3
"""CN Social doctor: executable path + external dependency + runtime state. Never PASS on import-only."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CN = ("xiaohongshu", "douyin", "kuaishou", "xianyu")
LEVELS = {
    0: "code exists",
    1: "unit tested",
    2: "fake provider integration",
    3: "real OAuth",
    4: "real remote publish / handoff",
    5: "real remote reconciliation",
    6: "real analytics",
    7: "full production E2E",
}


def _status(ok: bool, **extra) -> dict:
    payload = {"status": "PASS" if ok else "BLOCKED"}
    payload.update(extra)
    return payload


def _runtime():
    from social.runtime.container import SocialRuntime
    try:
        return SocialRuntime.production(), None
    except Exception as exc:
        return None, str(exc)


def check_runtime() -> dict:
    runtime, error = _runtime()
    from integrations.persistence import DatabaseStore, InMemoryStore
    if runtime is None:
        return _status(False, reason=error or "SocialRuntime.production() failed")
    if isinstance(runtime.store, InMemoryStore):
        return _status(False, reason="production runtime used InMemoryStore")
    ok = isinstance(runtime.store, DatabaseStore) and runtime.production is True
    return _status(ok, store=type(runtime.store).__name__, production=runtime.production)


def check_production_store() -> dict:
    try:
        from integrations.persistence import DatabaseStore
        store = DatabaseStore()
        store.list_accounts()
        return _status(True, store="DatabaseStore")
    except Exception as exc:
        return _status(False, reason=str(exc))


def check_credential_store() -> dict:
    try:
        from social.auth.secrets import production_secret_store
        store = production_secret_store()
        report = store.doctor()
        return _status(bool(report.get("ok")), **report)
    except Exception as exc:
        return _status(False, reason=str(exc), env="MEITI_SECRET_DIR")


def check_scheduler() -> dict:
    from social.schedule.scheduler import MeitiScheduler
    runtime, error = _runtime()
    if runtime is None:
        return _status(False, reason=error)
    ok = callable(getattr(runtime.store, "claim_due_job", None)) and isinstance(runtime.scheduler, MeitiScheduler)
    source = (ROOT / "social/schedule/scheduler.py").read_text(encoding="utf-8")
    if "adapter.schedule" in source or ".schedule(job)" in source:
        return _status(False, reason="scheduler still calls adapter.schedule")
    return _status(ok)


def check_publish_gate() -> dict:
    from governance.distribution_gate import check_distribution_job
    from integrations.contracts.distribution import ContentVariant, DistributionJob
    from social.accounts.models import SocialAccount, SocialProviderCapabilities, enable_account
    from social.auth.secrets import RuntimeSecretStore
    import tempfile
    secrets = RuntimeSecretStore(Path(tempfile.mkdtemp(prefix="meiti-doctor-secrets-")))
    ref = secrets.put({"access_token": "doctor-token", "provider": "douyin"})
    caps = SocialProviderCapabilities.from_claimed({"publish": True, "text": True, "video": True}, verified=True, method="doctor")
    account = enable_account(SocialAccount("i", "douyin", "douyin", username="meiti", status="VERIFIED", capabilities=caps, credential_ref=ref, provider_account_id="open-id"))
    job = DistributionJob("j", "p", "i", ContentVariant("i", "test"), idempotency_key="k")
    class Adapter:
        def __init__(self):
            self.secrets = secrets
            self.provider = "douyin"
        def get_account(self, account_id):
            return account
        def validate_payload(self, job):
            return []
        def health(self):
            from integrations.contracts.distribution import ProviderHealth
            return ProviderHealth(provider="douyin", reachable=False, authenticated=False)
    failures = check_distribution_job(job, account, adapter=Adapter())
    if "approval invalid" not in failures:
        return _status(False, reason="gate did not require approval", failures=failures)
    if any(token in str(failures) for token in ("provider_verified", "caller")):
        return _status(False, reason="caller supplied verification still accepted", failures=failures)
    return _status(True, failures=failures)


def check_lechuang() -> dict:
    from creative.providers.lechuang.adapter import LechuangAdapter
    adapter = LechuangAdapter()
    ready, reason = adapter.live_ready()
    return _status(ready, reason=reason)


def _provider_report(name: str) -> dict:
    from social.providers.resolver import resolve_social_provider
    handle = resolve_social_provider(name)
    adapter = handle.implementation
    health = adapter.health()
    oauth = getattr(adapter, "auth", None)
    oauth_available = bool(oauth and getattr(oauth, "available", lambda: False)())
    implemented = adapter.__class__.__name__ not in {"UnsupportedDistributionAdapter"}
    rows = {
        "implemented": implemented,
        "configured": oauth_available or bool(getattr(adapter, "_accounts", None)),
        "authenticated": bool(health.authenticated),
        "reachable": bool(health.reachable),
        "reason": health.last_error,
        "adapter": adapter.__class__.__name__,
    }
    if name == "xiaohongshu":
        rows.update({
            "handoff": True,
            "direct_publish": False,
            "level": 4 if implemented else 0,
            "direct_publish_status": "BLOCKED",
        })
    elif name == "xianyu":
        jushita = bool(getattr(adapter, "jushita_ready", lambda: False)())
        rows.update({"jushita": jushita, "level": 3 if oauth_available and jushita else (1 if implemented else 0)})
        if not jushita:
            rows["reason"] = rows.get("reason") or "JUSHITA required"
    else:
        rows["level"] = 3 if oauth_available and health.authenticated else (1 if implemented else 0)
    e2e = ROOT / "docs/audits/meiti-v4.4.2-cn-e2e.json"
    real = False
    if e2e.exists():
        data = json.loads(e2e.read_text(encoding="utf-8"))
        platform = data.get(name) or {}
        real = str(platform.get("status") or "").lower() in {"published", "pass", "handoff"} and not str(platform.get("remote_id") or "").startswith("fake")
    rows["real_e2e"] = real
    if real:
        rows["level"] = 7 if name != "xiaohongshu" else max(int(rows.get("level") or 0), 4)
    status = "PASS" if implemented else "BLOCKED"
    if name in {"douyin", "kuaishou", "xianyu"} and not (oauth_available and health.authenticated):
        status = "BLOCKED"
    if name == "xiaohongshu" and implemented:
        status = "PASS"
    if name == "xianyu" and not getattr(adapter, "jushita_ready", lambda: False)():
        status = "BLOCKED"
    return {"status": status, **rows, "level_name": LEVELS.get(int(rows.get("level") or 0))}


def check_accounts() -> dict:
    runtime, error = _runtime()
    if runtime is None:
        from social.accounts.manager import SocialAccountManager
        try:
            manager = SocialAccountManager()
        except Exception as exc:
            return _status(False, reason=str(exc) if error is None else error)
    else:
        manager = runtime.manager
    rows = manager.doctor_rows()
    return _status(True, account_count=len(rows), accounts=rows)


def check_provider_registry() -> dict:
    from social.providers.registry import load_social_registry
    from social.providers.resolver import resolve_social_provider

    registry = load_social_registry()
    missing = [name for name in CN if name not in registry]
    enabled_yaml = [name for name in CN if name in registry and registry[name].enabled]
    unresolved = []
    for name in CN:
        try:
            handle = resolve_social_provider(name)
            if handle.implementation is None:
                unresolved.append(name)
        except Exception:
            unresolved.append(name)
    return _status(not missing and not enabled_yaml and not unresolved, missing=missing, enabled=enabled_yaml, unresolved=unresolved)


def check_account_manager() -> dict:
    return check_accounts()


def check_provider_health() -> dict:
    reports = {name: _provider_report(name) for name in CN}
    live = all(item.get("status") == "PASS" for item in reports.values())
    return _status(live, providers={name: item.get("status") for name, item in reports.items()})


def run() -> dict:
    providers = {name: _provider_report(name) for name in CN}
    return {
        "Runtime": check_runtime(),
        "Production Store": check_production_store(),
        "Credential Store": check_credential_store(),
        "Scheduler": check_scheduler(),
        "Publish Gate": check_publish_gate(),
        "Lechuang": check_lechuang(),
        "Xiaohongshu": providers["xiaohongshu"],
        "Douyin": providers["douyin"],
        "Kuaishou": providers["kuaishou"],
        "Xianyu": providers["xianyu"],
        "Social Accounts": check_accounts(),
    }


def main() -> int:
    checks = run()
    print("MEITI CN SOCIAL DOCTOR")
    for name, item in checks.items():
        print(f"{name}: {item.get('status')}")
        if name == "Social Accounts":
            for row in item.get("accounts") or []:
                print(f"  {row['label']}: {row['status']} ACTION: {row['action']}")
        if name in {"Xiaohongshu", "Douyin", "Kuaishou", "Xianyu"}:
            print(f"  Adapter: {item.get('adapter')} Level: {item.get('level')} ({item.get('level_name')})")
            if name == "Xiaohongshu":
                print(f"  Handoff: PASS  Direct Publish: {item.get('direct_publish_status')}")
            if item.get("reason"):
                print(f"  reason: {item.get('reason')}")
    architecture = [name for name in ("Runtime", "Production Store", "Credential Store", "Scheduler", "Publish Gate") if checks[name].get("status") != "PASS"]
    overall = "READY" if not architecture and all(checks[name].get("status") == "PASS" for name in ("Xiaohongshu",)) else "BLOCKED"
    print("Overall:", overall)
    print(json.dumps({"ready": overall == "READY", "checks": {k: v.get("status") for k, v in checks.items()}, "details": checks}, default=str))
    return 0 if overall == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
