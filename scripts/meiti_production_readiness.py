#!/usr/bin/env python3
"""Honest production-readiness gate. External APIs never block CORE_PRODUCTION."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AUDIT_PATH = ROOT / "docs/audits/meiti-v4.8.1-production-readiness.json"


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
            "ARCHITECTURE": "BLOCKED_EXTERNAL",
            "CORE_PRODUCTION": "NOT_CONFIGURED",
            "POST_PRODUCTION": "NOT_VERIFIED",
            "FULL_LOOP": "NOT_VERIFIED",
            "error": str(exc),
        }
    payload["version"] = "4.8.1"
    payload["note"] = (
        "CORE_PRODUCTION=READY means the human production chain is code-complete. "
        "ANALYTICS/LEARNING/REAL E2E stay NOT_VERIFIED without real operator input."
    )
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    payload = run()
    print("MEITI_PRODUCTION_READINESS")
    print(f"CORE_PRODUCTION={payload.get('CORE_PRODUCTION')}")
    print(f"POST_PRODUCTION={payload.get('POST_PRODUCTION')}")
    print(f"FULL_LOOP={payload.get('FULL_LOOP')}")
    print(f"ANALYTICS={payload.get('ANALYTICS')}")
    print(f"LEARNING={payload.get('LEARNING')}")
    print(json.dumps(payload, indent=2, default=str))
    core = payload.get("CORE_PRODUCTION")
    architecture = payload.get("ARCHITECTURE")
    if architecture not in {"PASS", "NOT_CONFIGURED"} and core != "READY":
        return 1
    if core == "READY":
        return 0
    if architecture == "PASS" and core in {"READY", "PARTIAL"}:
        return 0
    if architecture == "NOT_CONFIGURED":
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
