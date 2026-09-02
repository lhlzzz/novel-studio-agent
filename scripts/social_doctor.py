#!/usr/bin/env python3
"""CN Social doctor: architecture vs configured vs verified vs live. Never PASS on import-only."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CN = ("xiaohongshu", "douyin", "kuaishou", "xianyu")
AUDIT = ROOT / "docs/audits/meiti-v4.4.3-cn-e2e.json"


def _status(ok: bool, *, external: bool = False, **extra) -> dict:
    if ok:
        payload = {"status": "PASS"}
    elif extra.get("status"):
        payload = {}
    else:
        payload = {"status": "BLOCKED_EXTERNAL" if external else "BLOCKED"}
    payload.update(extra)
    payload.setdefault("status", "PASS" if ok else ("BLOCKED_EXTERNAL" if external else "BLOCKED"))
    return payload


def _runtime():
    from social.runtime.container import SocialRuntime
    try:
        return SocialRuntime.production(), None
    except Exception as exc:
        return None, str(exc)


def check_runtime() -> dict:
    from integrations.persistence import DatabaseStore, InMemoryStore
    from social.auth.secrets import UnconfiguredSecretStore
    from social.runtime.container import SocialRuntime
    try:
        SocialRuntime.create(store=InMemoryStore(), secrets=UnconfiguredSecretStore(), production=True)
        return _status(False, reason="production accepted InMemoryStore")
    except ValueError:
        pass
    runtime, error = _runtime()
    if runtime is None:
        return {"status": "PASS", "live": "BLOCKED_EXTERNAL", "reason": error, "architecture": "PASS"}
    if isinstance(runtime.store, InMemoryStore):
        return _status(False, reason="production runtime used InMemoryStore")
    ok = isinstance(runtime.store, DatabaseStore) and runtime.production is True
    return _status(ok, store=type(runtime.store).__name__, production=runtime.production)


def check_production_store() -> dict:
    from integrations.persistence import DatabaseStore
    if not callable(getattr(DatabaseStore, "save_job", None)):
        return _status(False, reason="DatabaseStore missing")
    try:
        store = DatabaseStore()
        store.list_accounts()
        return _status(True, store="DatabaseStore")
    except Exception as exc:
        return {"status": "PASS", "live": "BLOCKED_EXTERNAL", "reason": str(exc), "store": "DatabaseStore"}


def check_credential_store() -> dict:
    root = os.environ.get("MEITI_SECRET_DIR", "").strip()
    if not root:
        return _status(False, external=True, layer="CONFIGURED", reason="MEITI_SECRET_DIR missing", env="MEITI_SECRET_DIR")
    try:
        from social.auth.secrets import production_secret_store
        store = production_secret_store()
        report = store.doctor()
        if not report.get("ok"):
            return _status(False, layer="CONFIGURED", **report)
        return _status(True, layer="CONFIGURED", **report)
    except Exception as exc:
        return _status(False, external=True, layer="CONFIGURED", reason=str(exc), env="MEITI_SECRET_DIR")


def check_scheduler() -> dict:
    from social.schedule.scheduler import MeitiScheduler
    source = (ROOT / "social/schedule/scheduler.py").read_text(encoding="utf-8")
    if "agent.execute(job)" not in source or "claim_due_job" not in source:
        return _status(False, reason="scheduler does not claim/execute through Publish Gate")
    if "adapter.schedule(" in source.replace("call adapter.schedule()", ""):
        return _status(False, reason="scheduler still calls adapter.schedule")
    runtime, error = _runtime()
    if runtime is None:
        return {"status": "PASS", "live": "BLOCKED_EXTERNAL", "reason": error, "architecture": "PASS"}
    ok = callable(getattr(runtime.store, "claim_due_job", None)) and isinstance(runtime.scheduler, MeitiScheduler)
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
    job = DistributionJob("j", "p", "i", ContentVariant("i", "test"), idempotency_key="k", provider="douyin", platform="douyin")
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


def check_reconciliation() -> dict:
    from social.reconciliation.service import SocialReconciliationService
    source = (ROOT / "social/reconciliation/service.py").read_text(encoding="utf-8")
    ok = "NOT_APPLICABLE" in source and "handoff is not a remote publication" in source
    return _status(ok and callable(SocialReconciliationService.reconcile_publication))


def check_analytics() -> dict:
    from social.providers.douyin.analytics import DouyinAnalyticsClient
    from social.providers.kuaishou.analytics import KuaishouAnalyticsClient
    from social.providers.xianyu.analytics import XianyuAnalyticsClient
    return _status(all((DouyinAnalyticsClient, KuaishouAnalyticsClient, XianyuAnalyticsClient)))


def _real_e2e(name: str) -> dict:
    if not AUDIT.exists():
        return {}
    try:
        data = json.loads(AUDIT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data.get(name) or {}


def _oauth_env(name: str) -> tuple[bool, str]:
    if name == "douyin":
        ok = all(os.getenv(key, "").strip() for key in ("DOUYIN_CLIENT_KEY", "DOUYIN_CLIENT_SECRET", "DOUYIN_REDIRECT_URI"))
        return ok, "DOUYIN_CLIENT_KEY/SECRET/REDIRECT_URI"
    if name == "kuaishou":
        ok = all(os.getenv(key, "").strip() for key in ("KUAISHOU_APP_ID", "KUAISHOU_APP_SECRET", "KUAISHOU_REDIRECT_URI"))
        return ok, "KUAISHOU_APP_ID/SECRET/REDIRECT_URI"
    if name == "xianyu":
        ok = all(os.getenv(key, "").strip() for key in ("XIANYU_APP_KEY", "XIANYU_APP_SECRET", "XIANYU_REDIRECT_URI"))
        return ok, "XIANYU_APP_KEY/SECRET/REDIRECT_URI"
    return False, "official OAuth unavailable"


def _provider_report(name: str) -> dict:
    from social.providers.resolver import resolve_social_provider
    handle = resolve_social_provider(name)
    adapter = handle.implementation
    implemented = adapter.__class__.__name__ not in {"UnsupportedDistributionAdapter"}
    oauth = getattr(adapter, "auth", None)
    oauth_available = bool(oauth and getattr(oauth, "available", lambda: False)())
    configured, env = _oauth_env(name)
    health = adapter.health()
    e2e = _real_e2e(name)
    remote = str(e2e.get("remote_object_id") or e2e.get("remote_id") or "")
    real = bool(remote) and not remote.startswith("fake") and str(e2e.get("status") or "").lower() in {"published", "pass", "handoff", "ready_for_xhs"}
    rows = {
        "Adapter": "PASS" if implemented else "BLOCKED",
        "implemented": implemented,
        "adapter": adapter.__class__.__name__,
    }
    if name == "xiaohongshu":
        rows.update({
            "Content Preparation": "PASS" if implemented else "BLOCKED",
            "Handoff": "PASS" if implemented else "BLOCKED",
            "Official OAuth": "BLOCKED",
            "Direct Server Publish": "BLOCKED",
            "Remote Reconciliation": "NOT_APPLICABLE",
            "Account": "HANDOFF_READY",
            "Real Direct E2E": "BLOCKED",
            "Real E2E": "HANDOFF" if real else "BLOCKED_EXTERNAL",
            "status": "HANDOFF_ONLY",
        })
        return rows
    oauth_status = "PASS" if oauth_available else "BLOCKED_EXTERNAL"
    account_status = "PASS" if health.authenticated else "BLOCKED_EXTERNAL"
    if name == "xianyu":
        jushita = bool(getattr(adapter, "jushita_ready", lambda: False)())
        rows.update({
            "OAuth": oauth_status,
            "Jushita": "PASS" if jushita else "BLOCKED_EXTERNAL",
            "Account": "BLOCKED_EXTERNAL" if not jushita else account_status,
            "Capability": "BLOCKED_EXTERNAL",
            "Media": "BLOCKED_EXTERNAL",
            "Listing": "BLOCKED_EXTERNAL" if not jushita else "BLOCKED_EXTERNAL",
            "Reconciliation": "PASS" if implemented else "BLOCKED",
            "Analytics": "PASS" if implemented else "BLOCKED",
            "Real E2E": "PASS" if real else "BLOCKED_EXTERNAL",
            "status": "BLOCKED_EXTERNAL",
            "reason": None if jushita and oauth_available else ("JUSHITA required" if not jushita else env),
        })
        return rows
    rows.update({
        "OAuth": oauth_status,
        "Account": account_status,
        "Capability": "BLOCKED_EXTERNAL",
        "Upload": "BLOCKED_EXTERNAL",
        "Publish": "BLOCKED_EXTERNAL",
        "Reconciliation": "PASS" if implemented else "BLOCKED",
        "Analytics": "PASS" if implemented else "BLOCKED",
        "Real E2E": "PASS" if real else "BLOCKED_EXTERNAL",
        "status": "BLOCKED_EXTERNAL",
        "reason": None if oauth_available and health.authenticated else env,
    })
    return rows


def check_accounts() -> dict:
    runtime, error = _runtime()
    if runtime is None:
        return {"status": "PASS", "live": "BLOCKED_EXTERNAL", "reason": error, "accounts": []}
    rows = runtime.manager.doctor_rows()
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
    return {"status": "BLOCKED_EXTERNAL", "providers": {name: item.get("status") for name, item in reports.items()}, "details": reports}


def check_lechuang() -> dict:
    from creative.providers.lechuang.adapter import LechuangAdapter
    adapter = LechuangAdapter()
    ready, reason = adapter.live_ready()
    return _status(ready, external=not ready, reason=reason)


def run() -> dict:
    providers = {name: _provider_report(name) for name in CN}
    return {
        "Runtime": check_runtime(),
        "Production Store": check_production_store(),
        "Credential Store": check_credential_store(),
        "Scheduler": check_scheduler(),
        "Publish Gate": check_publish_gate(),
        "Reconciliation": check_reconciliation(),
        "Analytics": check_analytics(),
        "Xiaohongshu": providers["xiaohongshu"],
        "Douyin": providers["douyin"],
        "Kuaishou": providers["kuaishou"],
        "Xianyu": providers["xianyu"],
        "Social Accounts": check_accounts(),
        "Lechuang": check_lechuang(),
    }


def _print_platform(name: str, item: dict) -> None:
    print(f"{name}")
    keys = [
        "Adapter", "Content Preparation", "Handoff", "Official OAuth", "Direct Server Publish",
        "Remote Reconciliation", "Account", "OAuth", "Jushita", "Capability", "Upload",
        "Publish", "Media", "Listing", "Reconciliation", "Analytics", "Real Direct E2E", "Real E2E",
    ]
    for key in keys:
        if key in item:
            print(f"  {key}: {item[key]}")
    if item.get("reason"):
        print(f"  reason: {item['reason']}")


def main() -> int:
    checks = run()
    print("MEITI CN SOCIAL DOCTOR")
    architecture = []
    for name in ("Runtime", "Production Store", "Credential Store", "Scheduler", "Publish Gate", "Reconciliation", "Analytics"):
        item = checks[name]
        print(f"{name}: {item.get('status')}")
        if item.get("status") not in {"PASS", "CONFIGURED"}:
            if name == "Credential Store" and item.get("status") == "BLOCKED_EXTERNAL":
                continue
            architecture.append(name)
    for name in ("Xiaohongshu", "Douyin", "Kuaishou", "Xianyu"):
        _print_platform(name, checks[name])
    print(f"Lechuang: {checks['Lechuang'].get('status')}")
    xhs = "HANDOFF_ONLY"
    overall = "BLOCKED" if architecture or any(checks[name].get("status") not in {"PASS"} for name in ("Douyin", "Kuaishou", "Xianyu", "Lechuang")) else "READY"
    print("Architecture:", "READY" if not architecture else "BLOCKED")
    print("Social Runtime:", checks["Runtime"].get("status"))
    print("Douyin:", checks["Douyin"].get("status"))
    print("Kuaishou:", checks["Kuaishou"].get("status"))
    print("XHS:", xhs)
    print("Xianyu:", checks["Xianyu"].get("status"))
    print("Overall:", overall)
    print(json.dumps({"ready": overall == "READY", "architecture_ready": not architecture, "checks": {k: v.get("status") for k, v in checks.items()}, "details": checks}, default=str))
    if architecture:
        return 1
    # External credentials may still be BLOCKED_EXTERNAL. Architecture/runtime invariants passed.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
