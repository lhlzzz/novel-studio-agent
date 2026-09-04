"""Production readiness. Capability is not evidence. External APIs never block CORE."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from content.models import ProductionReadinessRecord
from content.store import ContinuityStore, schema_ready


CORE_ACCOUNT_KEYS = (
    "ACCOUNT",
    "TASK",
    "PROMPT",
    "MANUAL_CREATIVE",
    "ASSET_IMPORT",
    "QA",
    "PACKAGE",
    "HANDOFF",
)
CORE_EPISODE_TYPES = (
    "CONTENT_PLAN",
    "PROMPT_GENERATION",
    "CREATIVE_EXECUTION",
    "ASSET_IMPORT",
    "QA",
    "PACKAGE",
    "HANDOFF",
)


def _system_capability(store: ContinuityStore) -> tuple[str, list[str]]:
    ready, missing = schema_ready(store.engine)
    try:
        from content.compiler import PromptCompiler
        from content.assets import PlatformAssetService
        from content.tasks import TaskOS
        from content.runtime import ContinuityRuntime
        from content.planner import EpisodePlanner

        owners = all((
            hasattr(PromptCompiler, "compile"),
            hasattr(PlatformAssetService, "import_asset"),
            hasattr(PlatformAssetService, "map_package_asset"),
            hasattr(TaskOS, "create_production_chain"),
            hasattr(ContinuityRuntime, "package_from_generation"),
            hasattr(ContinuityRuntime, "record_handoff"),
            hasattr(EpisodePlanner, "plan_next"),
        ))
    except Exception:
        owners = False
    status = "PASS" if ready and owners else "NOT_CONFIGURED"
    return status, missing


def _capability(system: str, account_configuration: str) -> str:
    if system != "PASS":
        return "NOT_CONFIGURED"
    if account_configuration == "PASS":
        return "PASS"
    if account_configuration == "PARTIAL":
        return "PARTIAL"
    return "NOT_CONFIGURED"


class ProductionReadinessService:
    def __init__(self, store: ContinuityStore | None = None) -> None:
        self.store = store or ContinuityStore()

    def evaluate(
        self,
        *,
        account_id: str | None = None,
        episode_id: str | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        system, missing_tables = _system_capability(self.store)
        accounts = self.store.list_accounts()
        if account_id:
            accounts = [item for item in accounts if item.account_id == account_id]
        account = accounts[0] if accounts else None
        detail: dict[str, Any] = {"missing_tables": missing_tables}
        checks: dict[str, str] = {}

        account_configuration = self._account_configuration(account)
        capability = _capability(system, account_configuration)
        checks["ACCOUNT"] = account_configuration
        checks["CHARACTER"] = "PASS" if account and account.character_id else ("PARTIAL" if account else "NOT_CONFIGURED")
        checks["WORLD"] = "PASS" if account and account.world_id else ("PARTIAL" if account else "NOT_CONFIGURED")
        series = self.store.active_series(account.account_id) if account else None
        checks["SERIES"] = "PASS" if series is not None else ("PARTIAL" if account else "NOT_CONFIGURED")
        checks["MEMORY"] = system
        checks["TASK"] = self._task_ready(account, episode_id, capability)
        prompt_status, prompt_ok = self._prompt_ready(account, episode_id, series, capability)
        checks["PROMPT"] = prompt_status
        checks["MANUAL_CREATIVE"] = "PASS" if capability == "PASS" and (prompt_ok or not episode_id) else capability
        checks["ASSET_IMPORT"] = capability
        checks["QA"] = capability
        checks["PACKAGE"] = self._package_ready(account, episode_id, capability)
        checks["HANDOFF"] = capability

        evidence = self.store.list_evidence(account_id=account.account_id) if account else []
        kinds = {item.kind for item in evidence}
        analytics_ok = any(item.kind == "ANALYTICS_IMPORTED" and item.analytics_id for item in evidence)
        learning_ok = any(item.kind == "LEARNING_WRITTEN" and item.learning_id and item.analytics_id for item in evidence)
        checks["ANALYTICS"] = "PASS" if analytics_ok else "NOT_VERIFIED"
        checks["LEARNING"] = "PASS" if learning_ok else "NOT_VERIFIED"
        detail["evidence_kinds"] = sorted(kinds)
        detail["account_id"] = account.account_id if account else None
        detail["episode_id"] = episode_id
        detail["lane"] = {
            "SYSTEM_CAPABILITY": "ARCHITECTURE",
            "ACCOUNT_CONFIGURATION": "CONFIGURATION",
            "CORE_PRODUCTION": "ARCHITECTURE",
            "PRODUCTION_EVIDENCE": "PRODUCTION_EVIDENCE",
            "POST_PRODUCTION": "PRODUCTION_EVIDENCE",
            "FULL_LOOP": "PRODUCTION_EVIDENCE",
        }

        core_pass = capability == "PASS" and all(checks.get(key) == "PASS" for key in CORE_ACCOUNT_KEYS)
        core = "READY" if core_pass else ("PARTIAL" if system == "PASS" and account else "NOT_CONFIGURED")
        post = "PASS" if checks["ANALYTICS"] == "PASS" and checks["LEARNING"] == "PASS" else "NOT_VERIFIED"
        full = "PASS" if core == "READY" and post == "PASS" else "NOT_VERIFIED"
        evidence_status = self._production_evidence(account, episode_id, evidence)
        payload = {
            "SYSTEM_CAPABILITY": system,
            "ARCHITECTURE": system,
            "CONFIGURATION": "PASS" if not missing_tables else "NOT_CONFIGURED",
            "ACCOUNT_CONFIGURATION": account_configuration,
            "ACCOUNT_OS": account_configuration,
            "TASK_OS": checks["TASK"],
            "CONTENT_CALENDAR": system,
            "CONTENT_PLANNER": system,
            "EPISODE_PLANNER": system,
            "PROMPT_RUNTIME": checks["PROMPT"],
            "MANUAL_LECHUANG": checks["MANUAL_CREATIVE"],
            "ASSET_IMPORT": checks["ASSET_IMPORT"],
            "ASSET_FRESHNESS": system,
            "ASSET_ISOLATION": system,
            "ASSET_LINEAGE": system,
            "TECHNICAL_QA": checks["QA"],
            "PACKAGE": checks["PACKAGE"],
            "HANDOFF": checks["HANDOFF"],
            "PRODUCTION_RUN": system,
            "PRODUCTION_EVIDENCE": evidence_status,
            "ANALYTICS": checks["ANALYTICS"],
            "LEARNING": checks["LEARNING"],
            "OBSIDIAN": system,
            "VECTOR": "NOT_VERIFIED",
            "USER_OVERRIDE": system,
            "MULTI_ACCOUNT": system,
            "MULTI_PLATFORM": system,
            "CORE_PRODUCTION": core,
            "POST_PRODUCTION": post,
            "FULL_LOOP": full,
            "checks": checks,
            "detail": detail,
        }
        if persist and system in {"PASS", "NOT_CONFIGURED"}:
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

    def _account_configuration(self, account) -> str:
        if account is None:
            return "NOT_CONFIGURED"
        required = {
            "account": True,
            "active": account.status == "ACTIVE",
            "character": bool(account.character_id),
            "world": bool(account.world_id),
            "series": bool(self.store.active_series(account.account_id) or account.series_id),
            "pool": self.store.get_pool(account_id=account.account_id, platform=account.platform) is not None,
            "dna": self.store.get_creative_dna(account.account_id, account.platform) is not None,
            "learning_profile": self.store.get_learning_profile(account.account_id, account.platform) is not None,
            "operating_state": self.store.get_operating_state(account.account_id) is not None,
        }
        if all(required.values()):
            return "PASS"
        if required["account"] and any(required.values()):
            return "PARTIAL"
        return "NOT_CONFIGURED"

    def _task_ready(self, account, episode_id: str | None, capability: str) -> str:
        if capability != "PASS":
            return capability
        if not episode_id:
            return "PASS"
        tasks = self.store.list_tasks(account_id=account.account_id, episode_id=episode_id)
        types = {item.task_type for item in tasks}
        return "PASS" if all(item in types for item in CORE_EPISODE_TYPES) else "PARTIAL"

    def _prompt_ready(self, account, episode_id: str | None, series, capability: str) -> tuple[str, bool]:
        if capability != "PASS":
            return capability, False
        if not episode_id:
            return "PASS", True
        episode = self.store.get_episode(episode_id, account_id=account.account_id)
        prompt = self.store.get_prompt(episode.prompt_id) if episode and episode.prompt_id else None
        if prompt is None and series:
            latest = self.store.latest_episode(series.series_id)
            prompt = self.store.get_prompt(latest.prompt_id) if latest and latest.prompt_id else None
        ok = bool(
            prompt
            and prompt.prompt_id
            and prompt.account_id
            and prompt.platform
            and prompt.episode_id
            and prompt.character_id
            and prompt.world_id
            and prompt.kind
            and prompt.copy_ready
            and prompt.prompt_hash
            and prompt.version
        )
        return ("PASS" if ok else "PARTIAL"), ok

    def _package_ready(self, account, episode_id: str | None, capability: str) -> str:
        if capability != "PASS":
            return capability
        if not episode_id:
            return "PASS"
        episode = self.store.get_episode(episode_id, account_id=account.account_id)
        if episode is None or not episode.content_package_id:
            return "PASS"
        mappings = self.store.list_package_assets(episode.content_package_id)
        primaries = [item for item in mappings if item.role == "PRIMARY"]
        if mappings and len(primaries) != 1:
            return "PARTIAL"
        return "PASS"

    def _production_evidence(self, account, episode_id: str | None, evidence: list) -> str:
        if not account:
            return "NOT_VERIFIED"
        series = self.store.active_series(account.account_id)
        episodes = self.store.list_episodes(series.series_id) if series else []
        if episode_id:
            episodes = [item for item in episodes if item.episode_id == episode_id]
        for episode in episodes:
            if not episode.production_run_id:
                continue
            run = self.store.get_production_run(episode.production_run_id)
            if run is None:
                continue
            complete = all((
                run.account_id,
                run.platform,
                run.task_id,
                run.episode_id,
                run.prompt_id,
                run.asset_id,
                run.package_id,
            ))
            kinds = {item.kind for item in evidence if item.episode_id == episode.episode_id}
            chain = (
                any(item.prompt_id for item in evidence if item.episode_id == episode.episode_id)
                and any(item.asset_id for item in evidence if item.episode_id == episode.episode_id)
                and ("QA_PASSED" in kinds or any((item.detail or {}).get("qa") == "pass" for item in evidence if item.episode_id == episode.episode_id))
                and "PACKAGE_READY" in kinds
                and any(kind in {"XHS_HANDOFF", "HANDOFF"} or str(kind).endswith("HANDOFF") for kind in kinds)
            )
            if complete and chain:
                return "PASS"
        return "NOT_VERIFIED"
