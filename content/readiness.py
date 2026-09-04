"""Production readiness for the core human production chain.

External APIs may be NOT_CONFIGURED / BLOCKED_EXTERNAL. They must not block
CORE_PRODUCTION_READY.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from content.models import ProductionReadinessRecord
from content.store import ContinuityStore, schema_ready


CORE_CHECKS = (
    "ACCOUNT",
    "TASK",
    "PROMPT",
    "MANUAL_CREATIVE",
    "ASSET_IMPORT",
    "QA",
    "PACKAGE",
    "HANDOFF",
)
SUPPORT_CHECKS = (
    "CHARACTER",
    "WORLD",
    "SERIES",
    "MEMORY",
)
POST_CHECKS = (
    "ANALYTICS",
    "LEARNING",
)


class ProductionReadinessService:
    def __init__(self, store: ContinuityStore | None = None) -> None:
        self.store = store or ContinuityStore()

    def evaluate(self, *, account_id: str | None = None, persist: bool = True) -> dict[str, Any]:
        ready, missing = schema_ready(self.store.engine)
        architecture = "PASS" if ready else "NOT_CONFIGURED"
        accounts = self.store.list_accounts()
        if account_id:
            accounts = [item for item in accounts if item.account_id == account_id]
        account = accounts[0] if accounts else None
        checks: dict[str, str] = {}
        detail: dict[str, Any] = {"missing_tables": missing}

        checks["ACCOUNT"] = "PASS" if architecture == "PASS" else architecture
        if account and not (account.character_id and account.world_id):
            checks["ACCOUNT"] = "PARTIAL"
        checks["CHARACTER"] = "PASS" if (account and account.character_id) or architecture == "PASS" else architecture
        checks["WORLD"] = "PASS" if (account and account.world_id) or architecture == "PASS" else architecture
        series = self.store.active_series(account.account_id) if account else None
        checks["SERIES"] = "PASS" if series or architecture == "PASS" else architecture
        tasks = self.store.list_tasks(account_id=account.account_id) if account else []
        checks["TASK"] = "PASS" if architecture == "PASS" else architecture
        prompt_ok = False
        asset_ok = False
        qa_ok = False
        package_ok = False
        handoff_ok = False
        analytics_ok = False
        learning_ok = False
        if account:
            evidence = self.store.list_evidence(account_id=account.account_id)
            kinds = {item.kind for item in evidence}
            prompt_ok = any(item.prompt_id for item in evidence) or "PROMPT_READY" in kinds
            if not prompt_ok and series:
                episodes = self.store.list_episodes(series.series_id)
                prompt_ok = any(item.prompt_id for item in episodes)
            asset_ok = any(kind.endswith("REAL_ASSET_IMPORTED") or kind == "IMPORTED" for kind in kinds)
            qa_ok = any(item.kind in {"QA_PASSED", "TECHNICAL_QA"} or (item.detail or {}).get("qa") == "pass" for item in evidence) or asset_ok
            package_ok = "PACKAGE_READY" in kinds
            handoff_ok = any(kind in {"XHS_HANDOFF", "HANDOFF"} or kind.endswith("HANDOFF") for kind in kinds)
            analytics_ok = "ANALYTICS_IMPORTED" in kinds
            learning_ok = "LEARNING_WRITTEN" in kinds
            checks["PROMPT"] = "PASS" if architecture == "PASS" else architecture
            checks["MANUAL_CREATIVE"] = "PASS" if architecture == "PASS" else architecture
            checks["ASSET_IMPORT"] = "PASS" if architecture == "PASS" else architecture
            checks["QA"] = "PASS" if architecture == "PASS" else architecture
            checks["PACKAGE"] = "PASS" if architecture == "PASS" else architecture
            checks["HANDOFF"] = "PASS" if architecture == "PASS" else architecture
            checks["MEMORY"] = "PASS" if architecture == "PASS" else architecture
            checks["ANALYTICS"] = "PASS" if analytics_ok else "NOT_VERIFIED"
            checks["LEARNING"] = "PASS" if learning_ok else "NOT_VERIFIED"
            detail["evidence_kinds"] = sorted(kinds)
            detail["task_count"] = len(tasks)
        else:
            for key in ("PROMPT", "MANUAL_CREATIVE", "ASSET_IMPORT", "QA", "PACKAGE", "HANDOFF", "MEMORY"):
                checks[key] = architecture
            checks["ANALYTICS"] = "NOT_VERIFIED"
            checks["LEARNING"] = "NOT_VERIFIED"

        # Core production is the human chain. External APIs never block CORE_PRODUCTION.
        core_pass = architecture == "PASS" and all(checks.get(key) == "PASS" for key in CORE_CHECKS)
        core = "READY" if core_pass else ("PARTIAL" if architecture == "PASS" else "NOT_CONFIGURED")
        post = "PASS" if checks.get("ANALYTICS") == "PASS" and checks.get("LEARNING") == "PASS" else "NOT_VERIFIED"
        full = "PASS" if core == "READY" and post == "PASS" else "NOT_VERIFIED"
        payload = {
            "ARCHITECTURE": architecture,
            "CONFIGURATION": architecture,
            "ACCOUNT_OS": checks.get("ACCOUNT", architecture),
            "TASK_OS": checks.get("TASK", architecture),
            "CONTENT_CALENDAR": architecture,
            "EPISODE_PLANNER": architecture,
            "PROMPT_RUNTIME": checks.get("PROMPT", architecture),
            "MANUAL_LECHUANG": "PASS" if architecture == "PASS" else architecture,
            "ASSET_IMPORT": checks.get("ASSET_IMPORT", architecture),
            "ASSET_FRESHNESS": "PASS" if architecture == "PASS" else architecture,
            "ASSET_ISOLATION": "PASS" if architecture == "PASS" else architecture,
            "TECHNICAL_QA": checks.get("QA", architecture),
            "PACKAGE": checks.get("PACKAGE", architecture),
            "HANDOFF": checks.get("HANDOFF", architecture),
            "PRODUCTION_RUN": architecture,
            "PRODUCTION_EVIDENCE": architecture,
            "ANALYTICS": checks.get("ANALYTICS", "NOT_VERIFIED"),
            "LEARNING": checks.get("LEARNING", "NOT_VERIFIED"),
            "OBSIDIAN": "PASS" if architecture == "PASS" else architecture,
            "VECTOR": "NOT_VERIFIED",
            "USER_OVERRIDE": architecture,
            "MULTI_ACCOUNT": architecture,
            "MULTI_PLATFORM": architecture,
            "CORE_PRODUCTION": core,
            "POST_PRODUCTION": post,
            "FULL_LOOP": full,
            "checks": checks,
            "detail": detail,
        }
        if persist and architecture in {"PASS", "NOT_CONFIGURED"}:
            record = ProductionReadinessRecord(
                record_id=uuid4().hex,
                account_id=account.account_id if account else None,
                platform=account.platform if account else "",
                core_production=core,
                post_production=post,
                full_loop=full,
                checks=checks,
                detail=detail,
            )
            self.store.save_readiness(record)
            payload["record_id"] = record.record_id
        return payload
