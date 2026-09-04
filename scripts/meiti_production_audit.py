#!/usr/bin/env python3
"""Honest production-loop audit. Code presence is never real Day evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AUDIT_PATH = ROOT / "docs/audits/meiti-v4.8.1-production-readiness.json"


def _status(ok: bool, *, missing: bool = False, evidence: bool = False) -> str:
    if missing:
        return "NOT_CONFIGURED"
    if evidence:
        return "PASS" if ok else "NOT_VERIFIED"
    return "PASS" if ok else "FAIL"


def code_audit() -> dict:
    required = {
        "content/models.py": ("class ProductionRun", "class AccountProfile", "class AccountOperatingState", "class CreatorTask", "class AnalyticsRecord", "CANONICAL_ANALYTICS_STORE"),
        "content/runtime.py": ("def compile_prompt", "def record_handoff", "def record_analytics", "def record_learning", "def dashboard", "def get_next_action"),
        "content/assets.py": ("EXISTING_ASSET", "CROSS_PLATFORM_ASSET_REUSE", "NO_PROMPT_REFERENCE", "class PlatformAssetService"),
        "content/compiler.py": ("COPY READY", "DUPLICATE_CONTENT", "class PromptCompiler"),
        "content/tasks.py": ("class TaskOS", "PRODUCTION_CHAIN"),
        "content/planner.py": ("class EpisodePlanner", "NEW_PRIMARY_REQUIRED"),
        "content/readiness.py": ("class ProductionReadinessService", "CORE_PRODUCTION"),
        "migrations/versions/0015_v481_production_ready_creator_os.py": ('revision = "0015_v481_production_ready_creator_os"',),
        "scripts/meiti.py": ("compile-prompt", "import-asset", "cmd_analytics_record", "cmd_learning_record", "cmd_task_next", "cmd_dashboard"),
    }
    missing = []
    for path, tokens in required.items():
        text = (ROOT / path).read_text(encoding="utf-8")
        for token in tokens:
            if token not in text:
                missing.append(f"{path}:{token}")
    return {"status": _status(not missing), "missing": missing, "lane": "ARCHITECTURE"}


def production_evidence() -> dict:
    try:
        from content.runtime import ContinuityRuntime
        from content.store import schema_ready
        from scripts.db.engine import engine

        ready, missing = schema_ready(engine)
        if not ready:
            return {"status": "NOT_CONFIGURED", "missing": missing, "lane": "CONFIGURATION"}
        runtime = ContinuityRuntime.production()
        kinds = set()
        for account in runtime.store.list_accounts():
            for item in runtime.store.list_evidence(account_id=account.account_id):
                kinds.add(item.kind)
        days = {
            "REAL_DAY_1": "DAY_001_REAL_ASSET_IMPORTED" in kinds,
            "REAL_DAY_2": "DAY_002_REAL_ASSET_IMPORTED" in kinds,
            "REAL_DAY_3": "DAY_003_REAL_ASSET_IMPORTED" in kinds,
            "HANDOFF": any(kind.endswith("HANDOFF") or kind == "XHS_HANDOFF" for kind in kinds),
            "ANALYTICS": "ANALYTICS_IMPORTED" in kinds,
            "LEARNING": "LEARNING_WRITTEN" in kinds,
        }
        return {
            "status": "PASS" if kinds else "NOT_VERIFIED",
            "lane": "PRODUCTION_EVIDENCE",
            "kinds": sorted(kinds),
            "days": {key: "PASS" if value else "NOT_VERIFIED" for key, value in days.items()},
        }
    except Exception as exc:
        return {"status": "BLOCKED_EXTERNAL", "error": str(exc), "lane": "EXTERNAL"}


def run() -> dict:
    evidence = production_evidence()
    days = evidence.get("days") or {}
    payload = {
        "version": "4.8.1",
        "CODE_AUDIT": code_audit(),
        "PRODUCTION_EVIDENCE": evidence,
        "REAL_DAY_1": {"status": days.get("REAL_DAY_1") or "NOT_VERIFIED", "lane": "PRODUCTION_EVIDENCE"},
        "REAL_DAY_2": {"status": days.get("REAL_DAY_2") or "NOT_VERIFIED", "lane": "PRODUCTION_EVIDENCE"},
        "REAL_DAY_3": {"status": days.get("REAL_DAY_3") or "NOT_VERIFIED", "lane": "PRODUCTION_EVIDENCE"},
        "HANDOFF": {"status": days.get("HANDOFF") or "NOT_VERIFIED", "lane": "PRODUCTION_EVIDENCE"},
        "PUBLICATION": {"status": "NOT_VERIFIED", "lane": "PRODUCTION_EVIDENCE", "note": "HANDOFF is not PUBLICATION"},
        "note": "Code tests PASS is never real production PASS. Operator Lechuang assets are required for REAL_DAY_X.",
    }
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    payload = run()
    print("MEITI_PRODUCTION_AUDIT")
    print(f"CODE_AUDIT={payload['CODE_AUDIT']['status']}")
    print(f"PRODUCTION_EVIDENCE={payload['PRODUCTION_EVIDENCE']['status']}")
    print(f"REAL_DAY_1={payload['REAL_DAY_1']['status']}")
    print(f"REAL_DAY_2={payload['REAL_DAY_2']['status']}")
    print(f"REAL_DAY_3={payload['REAL_DAY_3']['status']}")
    print(json.dumps(payload, indent=2, default=str))
    return 0 if payload["CODE_AUDIT"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
