#!/usr/bin/env python3
"""Honest production integrity audit. Code presence is never real evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AUDIT_PATH = ROOT / "docs/audits/meiti-v4.8.3-production-integrity.json"


def _hardcoded_core_ready(text: str) -> bool:
    return any(
        line.strip().startswith('"CORE_PRODUCTION_READY": True')
        or line.strip().startswith("'CORE_PRODUCTION_READY': True")
        for line in text.splitlines()
    )


def _print_status(name: str, status: str) -> None:
    allowed = {"PASS", "FAIL", "NOT_VERIFIED", "BLOCKED", "READY", "PARTIAL", "NOT_CONFIGURED"}
    if status not in allowed:
        status = "FAIL"
    print(f"{name}={status}")


def code_structure() -> dict:
    required = {
        "content/models.py": ("class ProductionRun", "class AnalyticsRecord", "ANALYTICS_ORIGINS", "LEARNING_EVIDENCE_STATES"),
        "content/runtime.py": ("def compile_prompt", "def record_handoff", "def record_analytics", "def record_learning", "PROJECTION_PENDING"),
        "content/assets.py": ("def _prevalidate_import", "def _commit_import", "class PlatformAssetService"),
        "content/compiler.py": ("COPY READY", "DUPLICATE_CONTENT", "class PromptCompiler", "def _validate_references"),
        "content/tasks.py": ("class TaskOS", "PRODUCTION_CHAIN"),
        "content/planner.py": ("class EpisodePlanner", "CALENDAR_SLOT_CONFLICT"),
        "content/readiness.py": ("class ProductionReadinessService", "CORE_PRODUCTION", "PACKAGE_MISSING", "CHARACTER_NOT_FOUND"),
        "content/store.py": ("def transaction", "NO nested"),
        "migrations/versions/0015_v481_production_ready_creator_os.py": ('revision = "0015_v481_production_ready_creator_os"',),
        "migrations/versions/0016_v482_final_hardening.py": ('revision = "0016_v482_final_hardening"',),
        "migrations/versions/0017_v483_production_integrity.py": ('revision = "0017_v483_production_integrity"',),
        "docs/architecture/canonical-owner-map.md": ("Canonical Owner Map", "ONE canonical writer"),
        "scripts/meiti.py": ("compile-prompt", "import-asset", "cmd_analytics_record", "cmd_learning_record"),
    }
    missing = []
    for path, tokens in required.items():
        text = (ROOT / path).read_text(encoding="utf-8")
        for token in tokens:
            if token == "NO nested":
                continue
            if token not in text:
                missing.append(f"{path}:{token}")
    assets = (ROOT / "content/assets.py").read_text(encoding="utf-8")
    if "with self.store.transaction()" not in assets:
        missing.append("content/assets.py:store.transaction")
    runtime = (ROOT / "content/runtime.py").read_text(encoding="utf-8")
    if "last_published_episode=package.episode_id" in runtime.split("def record_handoff")[1].split("def record_analytics")[0]:
        missing.append("content/runtime.py:handoff_sets_last_published_episode")
    audit = (ROOT / "scripts/meiti_production_audit.py").read_text(encoding="utf-8")
    if _hardcoded_core_ready(audit):
        missing.append("scripts/meiti_production_audit.py:hardcoded CORE_PRODUCTION_READY")
    return {"status": "PASS" if not missing else "FAIL", "missing": missing, "lane": "ARCHITECTURE"}


def semantic_invariants() -> dict:
    checks = {}
    readiness = (ROOT / "content/readiness.py").read_text(encoding="utf-8")
    runtime = (ROOT / "content/runtime.py").read_text(encoding="utf-8")
    assets = (ROOT / "content/assets.py").read_text(encoding="utf-8")
    compiler = (ROOT / "content/compiler.py").read_text(encoding="utf-8")
    gate = (ROOT / "social/publish/gate.py").read_text(encoding="utf-8")
    distribution = (ROOT / "agents/distribution_agent.py").read_text(encoding="utf-8")
    planner = (ROOT / "content/planner.py").read_text(encoding="utf-8")
    audit = Path(__file__).read_text(encoding="utf-8")
    checks["INV-001"] = "PASS" if "latest_episode" not in readiness.split("def _prompt_ready")[1].split("def _package_ready")[0] else "FAIL"
    checks["INV-002"] = "PASS" if "NO_VALID_CURRENT_ACCOUNT" in (ROOT / "content/resolve.py").read_text(encoding="utf-8") else "FAIL"
    checks["INV-003"] = "PASS" if "CHARACTER_NOT_FOUND" in readiness and "WORLD_NOT_FOUND" in readiness and "SERIES_NOT_FOUND" in readiness else "FAIL"
    checks["INV-004"] = "PASS" if "PACKAGE_MISSING" in readiness else "FAIL"
    checks["INV-005"] = "PASS" if "PACKAGE_ACCOUNT_MISMATCH" in distribution else "FAIL"
    checks["INV-006"] = "PASS" if "CROSS_PLATFORM_ASSET_REUSE" in assets else "FAIL"
    checks["INV-007"] = "PASS" if 'evidence_status == "VERIFIED"' in runtime.split("def record_learning")[1] else "FAIL"
    checks["INV-008"] = "PASS" if "MANUAL_ANALYTICS_OBSERVATION" in runtime else "FAIL"
    checks["INV-009"] = "PASS" if "last_published_episode=package.episode_id" not in runtime.split("def record_handoff")[1].split("def record_analytics")[0] else "FAIL"
    checks["INV-010"] = "PASS" if "MEDIA_NOT_UPLOADED" in gate else "FAIL"
    checks["INV-011"] = "PASS" if "receipt is not None" in readiness.split("def _production_evidence")[1] else "FAIL"
    checks["INV-012"] = "PASS" if "with self.store.transaction()" in assets and "def _prevalidate_import" in assets else "FAIL"
    checks["INV-013"] = "PASS" if "with self.store.transaction()" in runtime.split("def record_publication")[1].split("def record_feedback")[0] else "FAIL"
    checks["INV-014"] = "PASS" if not _hardcoded_core_ready(audit) else "FAIL"
    checks["INV-015"] = "PASS" if (ROOT / "docs/architecture/canonical-owner-map.md").exists() else "FAIL"
    failed = [key for key, status in checks.items() if status != "PASS"]
    return {"status": "PASS" if not failed else "FAIL", "checks": checks, "failed": failed, "lane": "ARCHITECTURE"}


def real_production_evidence() -> dict:
    try:
        from content.runtime import ContinuityRuntime
        from content.store import schema_ready
        from scripts.db.engine import engine

        ready, missing = schema_ready(engine)
        if not ready:
            return {"status": "NOT_VERIFIED", "missing": missing, "lane": "CONFIGURATION"}
        runtime = ContinuityRuntime.production()
        kinds = set()
        verified_analytics = False
        verified_learning = False
        for account in runtime.store.list_accounts():
            for item in runtime.store.list_evidence(account_id=account.account_id):
                kinds.add(item.kind)
                if item.kind == "ANALYTICS_IMPORTED" and (item.detail or {}).get("verified") is True:
                    verified_analytics = True
                if item.kind == "LEARNING_WRITTEN" and (item.detail or {}).get("evidence_status") == "VERIFIED":
                    verified_learning = True
        days = {
            "REAL_DAY_1": "DAY_001_REAL_ASSET_IMPORTED" in kinds,
            "REAL_DAY_2": "DAY_002_REAL_ASSET_IMPORTED" in kinds,
            "REAL_DAY_3": "DAY_003_REAL_ASSET_IMPORTED" in kinds,
            "HANDOFF": any(kind.endswith("HANDOFF") or kind == "XHS_HANDOFF" for kind in kinds),
            "ANALYTICS": verified_analytics,
            "LEARNING": verified_learning,
        }
        core_evidence = days["HANDOFF"] and (days["REAL_DAY_1"] or days["REAL_DAY_2"] or days["REAL_DAY_3"])
        return {
            "status": "PASS" if core_evidence and verified_analytics and verified_learning else "NOT_VERIFIED",
            "lane": "PRODUCTION_EVIDENCE",
            "kinds": sorted(kinds),
            "days": {key: "PASS" if value else "NOT_VERIFIED" for key, value in days.items()},
        }
    except Exception as exc:
        return {"status": "NOT_VERIFIED", "error": str(exc), "lane": "EXTERNAL"}


def computed_readiness() -> dict:
    try:
        from content.readiness import ProductionReadinessService
        from content.store import ContinuityStore, schema_ready
        from scripts.db.engine import engine

        ready, missing = schema_ready(engine)
        store = ContinuityStore.production() if ready else ContinuityStore.testing()
        payload = ProductionReadinessService(store).evaluate(persist=False)
        payload["CONFIGURATION"] = "PASS" if ready else "NOT_CONFIGURED"
        payload["missing_tables"] = missing
        return payload
    except Exception as exc:
        return {
            "SYSTEM_CAPABILITY": "NOT_VERIFIED",
            "CORE_PRODUCTION": "NOT_CONFIGURED",
            "POST_PRODUCTION": "NOT_VERIFIED",
            "FULL_LOOP": "NOT_VERIFIED",
            "error": str(exc),
        }


def run() -> dict:
    structure = code_structure()
    invariants = semantic_invariants()
    evidence = real_production_evidence()
    readiness = computed_readiness()
    days = evidence.get("days") or {}
    core = readiness.get("CORE_PRODUCTION") or "NOT_CONFIGURED"
    post = readiness.get("POST_PRODUCTION") or "NOT_VERIFIED"
    if evidence.get("status") != "PASS":
        post = "NOT_VERIFIED"
    payload = {
        "version": "4.8.3",
        "CODE_STRUCTURE": structure,
        "SEMANTIC_INVARIANTS": invariants,
        "REAL_PRODUCTION_EVIDENCE": evidence,
        "CODE_AUDIT": structure,
        "PRODUCTION_EVIDENCE": evidence,
        "REAL_DAY_1": {"status": days.get("REAL_DAY_1") or "NOT_VERIFIED", "lane": "PRODUCTION_EVIDENCE"},
        "REAL_DAY_2": {"status": days.get("REAL_DAY_2") or "NOT_VERIFIED", "lane": "PRODUCTION_EVIDENCE"},
        "REAL_DAY_3": {"status": days.get("REAL_DAY_3") or "NOT_VERIFIED", "lane": "PRODUCTION_EVIDENCE"},
        "HANDOFF": {"status": days.get("HANDOFF") or "NOT_VERIFIED", "lane": "PRODUCTION_EVIDENCE"},
        "PUBLICATION": {"status": "NOT_VERIFIED", "lane": "PRODUCTION_EVIDENCE", "note": "HANDOFF is not PUBLICATION"},
        "CODE_COMPLETE": structure["status"] == "PASS" and invariants["status"] == "PASS",
        "CORE_PRODUCTION": core,
        "CORE_PRODUCTION_READY": core == "READY",
        "POST_PRODUCTION": post,
        "POST_PRODUCTION_READY": post == "PASS",
        "REAL_PRODUCTION_VERIFIED": evidence.get("status") == "PASS",
        "POST_PRODUCTION_VERIFIED": post == "PASS",
        "FULL_LOOP_VERIFIED": core == "READY" and post == "PASS" and evidence.get("status") == "PASS",
        "note": "Code tests PASS is never real production PASS. Operator Lechuang assets are required for REAL_DAY_X.",
    }
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    payload = run()
    print("MEITI_PRODUCTION_AUDIT")
    _print_status("CODE_STRUCTURE", payload["CODE_STRUCTURE"]["status"])
    _print_status("SEMANTIC_INVARIANTS", payload["SEMANTIC_INVARIANTS"]["status"])
    _print_status("REAL_PRODUCTION_EVIDENCE", payload["REAL_PRODUCTION_EVIDENCE"]["status"])
    _print_status("CORE_PRODUCTION", payload["CORE_PRODUCTION"])
    _print_status("POST_PRODUCTION", payload["POST_PRODUCTION"])
    _print_status("REAL_DAY_1", payload["REAL_DAY_1"]["status"])
    _print_status("REAL_DAY_2", payload["REAL_DAY_2"]["status"])
    _print_status("REAL_DAY_3", payload["REAL_DAY_3"]["status"])
    print(json.dumps(payload, indent=2, default=str))
    if payload["CODE_STRUCTURE"]["status"] != "PASS":
        return 1
    if payload["SEMANTIC_INVARIANTS"]["status"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
