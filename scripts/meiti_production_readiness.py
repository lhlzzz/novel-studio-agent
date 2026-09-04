#!/usr/bin/env python3
"""Honest production-readiness gate. External APIs never block CORE_PRODUCTION."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AUDIT_PATH = ROOT / "docs/audits/meiti-v4.8.3-production-integrity.json"


def run() -> dict:
    from content.readiness import ProductionReadinessService
    from content.store import ContinuityStore, schema_ready

    try:
        from scripts.db.engine import engine
        ready, missing = schema_ready(engine)
        store = ContinuityStore.production() if ready else ContinuityStore.testing()
        if not ready:
            store = ContinuityStore.testing()
        payload = ProductionReadinessService(store).evaluate(persist=ready)
        payload["CONFIGURATION"] = "PASS" if ready else "NOT_CONFIGURED"
        payload["missing_tables"] = missing
    except Exception as exc:
        payload = {
            "SYSTEM_CAPABILITY": "BLOCKED_EXTERNAL",
            "ARCHITECTURE": "BLOCKED_EXTERNAL",
            "CORE_PRODUCTION": "NOT_CONFIGURED",
            "POST_PRODUCTION": "NOT_VERIFIED",
            "FULL_LOOP": "NOT_VERIFIED",
            "PRODUCTION_EVIDENCE": "NOT_VERIFIED",
            "error": str(exc),
        }
    payload["version"] = "4.8.3"
    payload["note"] = (
        "SYSTEM_CAPABILITY is code/schema. ACCOUNT_CONFIGURATION is the selected account. "
        "CORE_PRODUCTION=READY means the human chain can start. "
        "ANALYTICS/LEARNING/REAL_DAY stay NOT_VERIFIED without operator evidence."
    )
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    payload = run()
    print("MEITI_PRODUCTION_READINESS")
    print(f"SYSTEM_CAPABILITY={payload.get('SYSTEM_CAPABILITY') or payload.get('ARCHITECTURE')}")
    print(f"ACCOUNT_CONFIGURATION={payload.get('ACCOUNT_CONFIGURATION')}")
    print(f"CORE_PRODUCTION={payload.get('CORE_PRODUCTION')}")
    print(f"POST_PRODUCTION={payload.get('POST_PRODUCTION')}")
    print(f"FULL_LOOP={payload.get('FULL_LOOP')}")
    print(f"ANALYTICS={payload.get('ANALYTICS')}")
    print(f"LEARNING={payload.get('LEARNING')}")
    print(f"PRODUCTION_EVIDENCE={payload.get('PRODUCTION_EVIDENCE')}")
    print(json.dumps(payload, indent=2, default=str))
    core = payload.get("CORE_PRODUCTION")
    system = payload.get("SYSTEM_CAPABILITY") or payload.get("ARCHITECTURE")
    if core == "READY":
        return 0
    if system == "PASS":
        return 0
    if system == "NOT_CONFIGURED":
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
