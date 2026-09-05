"""Production readiness. Capability is not evidence. External APIs never block CORE."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from content.models import IsolationError, ProductionReadinessRecord
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
        from content.planner import CreatorBrain, EpisodePlanner

        owners = all((
            hasattr(PromptCompiler, "compile"),
            hasattr(PlatformAssetService, "import_asset"),
            hasattr(PlatformAssetService, "map_package_asset"),
            hasattr(TaskOS, "create_production_chain"),
            hasattr(ContinuityRuntime, "package_from_generation"),
            hasattr(ContinuityRuntime, "record_handoff"),
            hasattr(ContinuityRuntime, "produce_today"),
            hasattr(EpisodePlanner, "plan_next"),
            hasattr(CreatorBrain, "decide"),
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

        account_configuration, config_codes = self._account_configuration(account)
        capability = _capability(system, account_configuration)
        checks["ACCOUNT"] = account_configuration
        checks["CHARACTER"] = config_codes.get("character") or ("NOT_CONFIGURED" if not account else "FAIL")
        checks["WORLD"] = config_codes.get("world") or ("NOT_CONFIGURED" if not account else "FAIL")
        series = self.store.active_series(account.account_id) if account else None
        checks["SERIES"] = config_codes.get("series") or ("NOT_CONFIGURED" if not account else "FAIL")
        checks["MEMORY"] = system
        checks["TASK"] = self._task_ready(account, episode_id, capability)
        prompt_status, prompt_ok = self._prompt_ready(account, episode_id, capability)
        checks["PROMPT"] = prompt_status
        checks["MANUAL_CREATIVE"] = "PASS" if capability == "PASS" and (prompt_ok or not episode_id) else ("FAIL" if episode_id and not prompt_ok else capability)
        checks["ASSET_IMPORT"] = capability
        checks["QA"] = capability
        checks["PACKAGE"] = self._package_ready(account, episode_id, capability)
        checks["HANDOFF"] = capability
        detail["error_codes"] = {key: value for key, value in config_codes.items() if value not in {"PASS", "PARTIAL"}}

        evidence = self.store.list_evidence(account_id=account.account_id) if account else []
        kinds = {item.kind for item in evidence}
        analytics_ok = any(
            item.kind == "ANALYTICS_IMPORTED"
            and item.analytics_id
            and (item.detail or {}).get("verified") is True
            for item in evidence
        )
        learning_ok = any(
            item.kind == "LEARNING_WRITTEN"
            and item.learning_id
            and item.analytics_id
            and (item.detail or {}).get("evidence_status") == "VERIFIED"
            for item in evidence
        )
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
            "CORE_CONTENT_PRODUCTION": core,
            "CREATOR_IDENTITY": account_configuration if account else "NOT_CONFIGURED",
            "CREATOR_STATE": "PASS" if account and self.store.get_creator_state(account.account_id) else ("NOT_CONFIGURED" if not account else "PARTIAL"),
            "CREATOR_STRATEGY": "PASS" if account and self.store.current_strategy(account.account_id) else ("NOT_CONFIGURED" if not account else "PARTIAL"),
            "CONTENT_NOVELTY": system,
            "CONTENT_PORTFOLIO": system,
            "SERIES_ENGINE": "PASS" if account and series else ("NOT_CONFIGURED" if not account else "PARTIAL"),
            "DECISION_TRACE": system,
            "PRODUCTION_MEMORY": system,
            "EXTERNAL_CONNECTION": "NOT_CONNECTED" if account and not (self.store.get_platform_connection(account.account_id, account.platform) and self.store.get_platform_connection(account.account_id, account.platform).connected) else ("PASS" if account else "NOT_CONFIGURED"),
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

    def _account_configuration(self, account) -> tuple[str, dict[str, str]]:
        codes: dict[str, str] = {}
        if account is None:
            return "NOT_CONFIGURED", codes
        if account.status != "ACTIVE":
            codes["account"] = "NO_VALID_CURRENT_ACCOUNT"
            return "FAIL", codes
        codes["account"] = "PASS"
        codes["character"] = self._entity_ready(
            account.character_id,
            fetcher=lambda entity_id: self.store.get_character(entity_id, account_id=account.account_id),
            missing="CHARACTER_NOT_FOUND",
            mismatch="CHARACTER_SCOPE_MISMATCH",
            account_id=account.account_id,
        )
        codes["world"] = self._entity_ready(
            account.world_id,
            fetcher=lambda entity_id: self.store.get_world(entity_id, account_id=account.account_id),
            missing="WORLD_NOT_FOUND",
            mismatch="WORLD_SCOPE_MISMATCH",
            account_id=account.account_id,
        )
        series = None
        if account.series_id:
            try:
                series = self.store.get_series(account.series_id, account_id=account.account_id)
            except IsolationError:
                series = None
                codes["series"] = "SERIES_SCOPE_MISMATCH"
            if "series" not in codes:
                if series is None:
                    codes["series"] = "SERIES_NOT_FOUND"
                elif series.account_id != account.account_id:
                    codes["series"] = "SERIES_SCOPE_MISMATCH"
                elif series.status not in {"ACTIVE", "DRAFT"}:
                    codes["series"] = "SERIES_SCOPE_MISMATCH"
                else:
                    codes["series"] = "PASS"
        else:
            series = self.store.active_series(account.account_id)
            codes["series"] = "PASS" if series is not None else "NOT_CONFIGURED"
        required = {
            "account": codes["account"] == "PASS",
            "active": account.status == "ACTIVE",
            "character": codes.get("character") == "PASS",
            "world": codes.get("world") == "PASS",
            "series": codes.get("series") == "PASS",
            "pool": self.store.get_pool(account_id=account.account_id, platform=account.platform) is not None,
            "dna": self.store.get_creative_dna(account.account_id, account.platform) is not None,
            "learning_profile": self.store.get_learning_profile(account.account_id, account.platform) is not None,
            "operating_state": self.store.get_operating_state(account.account_id) is not None,
        }
        if all(required.values()):
            return "PASS", codes
        if any(codes.get(key) in {"CHARACTER_NOT_FOUND", "CHARACTER_SCOPE_MISMATCH", "WORLD_NOT_FOUND", "WORLD_SCOPE_MISMATCH", "SERIES_NOT_FOUND", "SERIES_SCOPE_MISMATCH"} for key in codes):
            return "FAIL", codes
        if required["account"] and any(required.values()):
            return "PARTIAL", codes
        return "NOT_CONFIGURED", codes

    def _entity_ready(self, entity_id: str | None, *, fetcher, missing: str, mismatch: str, account_id: str) -> str:
        if not entity_id:
            return "NOT_CONFIGURED"
        try:
            entity = fetcher(entity_id)
        except IsolationError:
            return mismatch
        except Exception:
            return missing
        if entity is None:
            return missing
        if getattr(entity, "account_id", account_id) != account_id:
            return mismatch
        status = getattr(entity, "status", "ACTIVE")
        if status not in {"ACTIVE", "DRAFT"}:
            return mismatch
        return "PASS"

    def _task_ready(self, account, episode_id: str | None, capability: str) -> str:
        if capability != "PASS":
            return capability
        if not episode_id:
            return "PASS"
        episode = self.store.get_episode(episode_id, account_id=account.account_id)
        if episode is None:
            return "FAIL"
        tasks = self.store.list_tasks(account_id=account.account_id, episode_id=episode_id)
        if not tasks:
            return "TASK_MISSING"
        valid_status = {"TODO", "READY", "IN_PROGRESS", "WAITING_OPERATOR", "WAITING_EXTERNAL", "DONE"}
        valid_priority = {"CRITICAL", "HIGH", "NORMAL", "LOW"}
        by_id = {item.task_id: item for item in tasks}
        for item in tasks:
            if item.account_id != account.account_id:
                return "TASK_ACCOUNT_MISMATCH"
            if item.platform != account.platform:
                return "TASK_PLATFORM_MISMATCH"
            if item.episode_id and item.episode_id != episode_id:
                return "TASK_EPISODE_MISMATCH"
            if item.status not in valid_status:
                return "TASK_STATUS_INVALID"
            if item.priority not in valid_priority:
                return "TASK_PRIORITY_INVALID"
            if episode.production_run_id and item.production_run_id and item.production_run_id != episode.production_run_id:
                return "TASK_PRODUCTION_RUN_MISMATCH"
            for dep in item.dependencies or ():
                if dep not in by_id:
                    return "TASK_DEPENDENCY_INVALID"
        types = {item.task_type for item in tasks}
        if not all(item in types for item in CORE_EPISODE_TYPES):
            return "TASK_CHAIN_INCOMPLETE"
        return "PASS"

    def _prompt_ready(self, account, episode_id: str | None, capability: str) -> tuple[str, bool]:
        if capability != "PASS":
            return capability, False
        if not episode_id:
            return "PASS", True
        episode = self.store.get_episode(episode_id, account_id=account.account_id)
        if episode is None or not episode.prompt_id:
            return "FAIL", False
        prompt = self.store.get_prompt(episode.prompt_id)
        ok = bool(
            prompt
            and prompt.prompt_id
            and prompt.account_id == account.account_id
            and prompt.platform == account.platform
            and prompt.episode_id == episode.episode_id
            and prompt.character_id
            and prompt.world_id
            and prompt.kind
            and prompt.copy_ready
            and prompt.prompt_hash
            and prompt.version
        )
        return ("PASS" if ok else "FAIL"), ok

    def _package_ready(self, account, episode_id: str | None, capability: str) -> str:
        if capability != "PASS":
            return capability
        if not episode_id:
            return "PASS"
        episode = self.store.get_episode(episode_id, account_id=account.account_id)
        if episode is None:
            return "FAIL"
        if not episode.content_package_id:
            return "PACKAGE_MISSING"
        package = self.store.get_package(episode.content_package_id)
        if package is None:
            return "PACKAGE_MISSING"
        if package.account_id != episode.account_id:
            return "PACKAGE_ACCOUNT_MISMATCH"
        if package.platform and package.platform != account.platform:
            return "PACKAGE_PLATFORM_MISMATCH"
        if package.episode_id and package.episode_id != episode.episode_id:
            return "PACKAGE_EPISODE_MISMATCH"
        mappings = self.store.list_package_assets(episode.content_package_id)
        primaries = [item for item in mappings if item.role == "PRIMARY"]
        if len(primaries) != 1:
            return "PACKAGE_INCOMPLETE"
        primary = self.store.get_media_asset(primaries[0].asset_id)
        if primary is None:
            return "PACKAGE_INCOMPLETE"
        if (primary.lifecycle or "").upper() in {"ARCHIVED", "REJECTED", "QA_FAILED"}:
            return "PACKAGE_STALE"
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
            receipt = self.store.get_receipt_for_asset(run.asset_id) if run.asset_id else None
            complete = all((
                run.account_id,
                run.platform,
                run.task_id,
                run.episode_id,
                run.prompt_id,
                run.asset_id,
                run.package_id,
                receipt is not None,
                receipt.prompt_id if receipt else None,
                receipt.tool if receipt else None,
                receipt.model if receipt else None,
                receipt.production_run_id if receipt else None,
            ))
            kinds = {item.kind for item in evidence if item.episode_id == episode.episode_id}
            chain = (
                any(item.prompt_id for item in evidence if item.episode_id == episode.episode_id)
                and any(item.asset_id for item in evidence if item.episode_id == episode.episode_id)
                and receipt is not None
                and ("QA_PASSED" in kinds or any((item.detail or {}).get("qa") == "pass" for item in evidence if item.episode_id == episode.episode_id))
                and "PACKAGE_READY" in kinds
                and any(kind in {"XHS_HANDOFF", "HANDOFF"} or str(kind).endswith("HANDOFF") for kind in kinds)
            )
            if complete and chain:
                return "PASS"
        return "NOT_VERIFIED"
