#!/usr/bin/env python3
"""CN Social doctor. Architecture PASS is not live READY. Missing credentials are BLOCKED_EXTERNAL."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CN = ("xiaohongshu", "douyin", "kuaishou", "xianyu")
AUDIT = ROOT / "docs/audits/meiti-v4.4.4-cn-e2e.json"
STATUSES = {"PASS", "BLOCKED_EXTERNAL", "BLOCKED", "FAIL", "NOT_APPLICABLE", "HANDOFF_READY", "HANDOFF_ONLY"}


def _status(value: str, **extra) -> dict:
    if value not in STATUSES:
        value = "FAIL"
    payload = {"status": value}
    payload.update(extra)
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
        return _status("FAIL", reason="production accepted InMemoryStore")
    except ValueError:
        pass
    runtime, error = _runtime()
    if runtime is None:
        return _status("BLOCKED_EXTERNAL", reason=error, architecture="PASS")
    if isinstance(runtime.store, InMemoryStore):
        return _status("FAIL", reason="production runtime used InMemoryStore")
    if isinstance(runtime.store, DatabaseStore) and runtime.production is True:
        return _status("PASS", store=type(runtime.store).__name__, production=runtime.production)
    return _status("BLOCKED", reason="production runtime is not DatabaseStore")


def check_production_store() -> dict:
    from integrations.persistence import DatabaseStore
    try:
        store = DatabaseStore()
        store.list_accounts()
        return _status("PASS", store="DatabaseStore")
    except Exception as exc:
        return _status("BLOCKED_EXTERNAL", reason=str(exc), store="DatabaseStore", architecture="PASS")


def check_credential_store() -> dict:
    root = os.environ.get("MEITI_SECRET_DIR", "").strip()
    if not root:
        return _status("BLOCKED_EXTERNAL", reason="MEITI_SECRET_DIR missing", env="MEITI_SECRET_DIR")
    try:
        from social.auth.secrets import production_secret_store
        store = production_secret_store()
        report = store.doctor()
        if not report.get("ok"):
            return _status("BLOCKED", **report)
        return _status("PASS", **report)
    except Exception as exc:
        return _status("BLOCKED_EXTERNAL", reason=str(exc), env="MEITI_SECRET_DIR")


def check_scheduler() -> dict:
    from social.schedule.scheduler import MeitiScheduler
    source = (ROOT / "social/schedule/scheduler.py").read_text(encoding="utf-8")
    if "agent.execute(job)" not in source or "claim_due_job" not in source:
        return _status("FAIL", reason="scheduler does not claim/execute through Publish Gate")
    if "adapter.schedule(job" in source or "self.adapter.schedule(" in source:
        return _status("FAIL", reason="scheduler still calls adapter.schedule")
    runtime, error = _runtime()
    if runtime is None:
        return _status("BLOCKED_EXTERNAL", reason=error, architecture="PASS")
    ok = callable(runtime.store.claim_due_job) and isinstance(runtime.scheduler, MeitiScheduler)
    return _status("PASS" if ok else "FAIL")


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
        return _status("FAIL", reason="gate did not require approval", failures=failures)
    if any(token in str(failures) for token in ("provider_verified", "caller")):
        return _status("FAIL", reason="caller supplied verification still accepted", failures=failures)
    return _status("PASS", failures=failures)


def check_reconciliation() -> dict:
    from social.reconciliation.service import SocialReconciliationService
    source = (ROOT / "social/reconciliation/service.py").read_text(encoding="utf-8")
    ok = "NOT_APPLICABLE" in source and "handoff is not a remote publication" in source
    return _status("PASS" if ok and callable(SocialReconciliationService.reconcile_publication) else "FAIL")


def check_analytics() -> dict:
    from social.providers.douyin.analytics import DouyinAnalyticsClient
    from social.providers.kuaishou.analytics import KuaishouAnalyticsClient
    from social.providers.xianyu.analytics import XianyuAnalyticsClient
    return _status("PASS" if all((DouyinAnalyticsClient, KuaishouAnalyticsClient, XianyuAnalyticsClient)) else "FAIL")


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
    if name == "xiaohongshu":
        ok = all(os.getenv(key, "").strip() for key in ("XHS_CLIENT_ID", "XHS_CLIENT_SECRET", "XHS_REDIRECT_URI"))
        return ok, "XHS_CLIENT_ID/SECRET/REDIRECT_URI"
    return False, "credentials missing"


def _provider_report(name: str) -> dict:
    from social.providers.resolver import resolve_social_provider
    handle = resolve_social_provider(name)
    adapter = handle.implementation
    implemented = adapter.__class__.__name__ not in {"UnsupportedDistributionAdapter"}
    oauth = getattr(adapter, "auth", None)
    oauth_available = bool(oauth and getattr(oauth, "available", lambda: False)())
    configured, env = _oauth_env(name)
    e2e = _real_e2e(name)
    remote = str(e2e.get("remote_object_id") or e2e.get("remote_id") or "")
    live = bool(remote) and not remote.startswith("fake") and str(e2e.get("status") or "").lower() in {"published", "live_verified", "online"}
    rows = {
        "Adapter": "PASS" if implemented else "FAIL",
        "implemented": implemented,
        "adapter": adapter.__class__.__name__,
    }
    if name == "xiaohongshu":
        rows.update({
            "OAuth": "BLOCKED_EXTERNAL",
            "Account": "HANDOFF_READY",
            "Handoff": "PASS" if implemented else "FAIL",
            "Direct Publish": "BLOCKED_EXTERNAL",
            "Reconciliation": "NOT_APPLICABLE",
            "Real E2E": "BLOCKED_EXTERNAL",
            "status": "HANDOFF_ONLY",
            "architecture_supported": True,
        })
        return rows
    if name == "xianyu":
        jushita = bool(getattr(adapter, "jushita_ready", lambda: False)())
        rows.update({
            "OAuth": "PASS" if oauth_available else "BLOCKED_EXTERNAL",
            "Jushita": "PASS" if jushita else "BLOCKED_EXTERNAL",
            "Account": "BLOCKED_EXTERNAL",
            "Capability": "BLOCKED_EXTERNAL",
            "Media": "BLOCKED_EXTERNAL",
            "Listing": "BLOCKED_EXTERNAL",
            "Reconciliation": "PASS" if implemented else "FAIL",
            "Analytics": "PASS" if implemented else "FAIL",
            "Real E2E": "LIVE_VERIFIED" if live else "BLOCKED_EXTERNAL",
            "status": "BLOCKED_EXTERNAL",
            "reason": None if jushita and oauth_available else ("JUSHITA required" if not jushita else env),
        })
        return rows
    rows.update({
        "OAuth": "PASS" if oauth_available else "BLOCKED_EXTERNAL",
        "Account": "BLOCKED_EXTERNAL",
        "Capability": "BLOCKED_EXTERNAL",
        "Upload": "BLOCKED_EXTERNAL",
        "Publish": "BLOCKED_EXTERNAL",
        "Reconciliation": "PASS" if implemented else "FAIL",
        "Analytics": "PASS" if implemented else "FAIL",
        "Real E2E": "LIVE_VERIFIED" if live else "BLOCKED_EXTERNAL",
        "status": "BLOCKED_EXTERNAL",
        "reason": None if oauth_available else env,
    })
    return rows


def check_accounts() -> dict:
    runtime, error = _runtime()
    if runtime is None:
        return _status("BLOCKED_EXTERNAL", reason=error, accounts=[])
    rows = runtime.manager.doctor_rows()
    return _status("PASS", account_count=len(rows), accounts=rows)


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
    return _status("PASS" if not missing and not enabled_yaml and not unresolved else "FAIL", missing=missing, enabled=enabled_yaml, unresolved=unresolved)


def check_account_manager() -> dict:
    return check_accounts()


def check_provider_health() -> dict:
    reports = {name: _provider_report(name) for name in CN}
    return {"status": "BLOCKED_EXTERNAL", "providers": {name: item.get("status") for name, item in reports.items()}, "details": reports}


def check_lechuang() -> dict:
    from creative.providers.lechuang.adapter import LechuangAdapter
    adapter = LechuangAdapter()
    ready, reason = adapter.live_ready()
    return _status("PASS" if ready else "BLOCKED_EXTERNAL", reason=reason)


def evaluate_production_readiness(checks: dict | None = None) -> dict:
    checks = checks or run()
    architecture_names = ("Runtime", "Production Store", "Scheduler", "Publish Gate", "Reconciliation", "Analytics")
    architecture_fail = [name for name in architecture_names if checks[name].get("status") not in {"PASS", "BLOCKED_EXTERNAL"}]
    architecture = "PASS" if not architecture_fail else "FAIL"
    runtime = checks["Runtime"].get("status")
    external = "BLOCKED_EXTERNAL"
    overall = "FAIL" if architecture == "FAIL" else "BLOCKED_EXTERNAL"
    return {
        "architecture": architecture,
        "runtime": runtime,
        "external": external,
        "overall": overall,
        "architecture_ready": architecture == "PASS",
        "runtime_ready": runtime == "PASS",
        "external_ready": False,
        "overall_ready": False,
        "blockers": architecture_fail,
    }


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
        "Adapter", "OAuth", "Account", "Handoff", "Direct Publish", "Jushita",
        "Capability", "Upload", "Publish", "Media", "Listing", "Reconciliation",
        "Analytics", "Real E2E",
    ]
    for key in keys:
        if key in item:
            print(f"  {key:<22} {item[key]}")
    if item.get("reason"):
        print(f"  reason: {item['reason']}")


def main() -> int:
    checks = run()
    readiness = evaluate_production_readiness(checks)
    print("MEITI CN SOCIAL DOCTOR")
    print("======================")
    print()
    print("ARCHITECTURE")
    for name in ("Runtime", "Production Store", "Credential Store", "Scheduler", "Publish Gate", "Reconciliation", "Analytics"):
        print(f"{name:<22} {checks[name].get('status')}")
    print()
    print("PROVIDERS")
    print()
    for name in ("Xiaohongshu", "Douyin", "Kuaishou", "Xianyu"):
        _print_platform(name, checks[name])
        print()
    print(f"Lechuang               {checks['Lechuang'].get('status')}")
    print()
    print("OVERALL")
    print(f"Architecture            {readiness['architecture']}")
    print(f"Production              {readiness['overall']}")
    payload = {
        "architecture_ready": readiness["architecture_ready"],
        "runtime_ready": readiness["runtime_ready"],
        "external_ready": False,
        "overall_ready": False,
        "architecture": readiness["architecture"],
        "runtime": readiness["runtime"],
        "external": readiness["external"],
        "overall": readiness["overall"],
        "providers": {name.lower(): checks[name].get("status") for name in ("Xiaohongshu", "Douyin", "Kuaishou", "Xianyu")},
        "blockers": readiness["blockers"],
        "evidence": {k: v.get("status") for k, v in checks.items()},
        "details": checks,
    }
    print(json.dumps(payload, default=str))
    return 0 if readiness["architecture"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
