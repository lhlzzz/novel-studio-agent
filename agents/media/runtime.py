"""Media agent selects and submits creative workflows. It does not call providers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from creative.schemas import CREATIVE_MEMORY_CODES
from creative.workflow.engine import CreativeWorkflowEngine
from creative.workflow.resolver import resolve_from_requirement
from memory.writeback import write_patterns


class MediaAgent:
    name = "media-agent"
    owner = "media"
    capabilities = ("validate", "prepare", "hash", "generate", "workflow")
    state_store = "postgres:agent_records"
    tests = ("tests/unit/test_media_upload.py", "tests/creative/test_workflow_runtime.py")

    def __init__(self, *, engine: CreativeWorkflowEngine | None = None, runtime=None) -> None:
        self.engine = engine
        self.runtime = runtime

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        if self._is_generate(task):
            return self._generate(task)
        return self._hash_local(task)

    def _is_generate(self, task: dict[str, Any]) -> bool:
        if task.get("kind") in {"generate", "create_video", "creative"}:
            return True
        return any(task.get(key) for key in ("brief", "creative_brief", "creative_requirement", "workflow_id"))

    def _engine(self, *, allow_mock: bool) -> CreativeWorkflowEngine:
        if self.engine is not None:
            return self.engine
        if self.runtime is not None:
            return self.runtime.engine
        from creative.runtime.container import CreativeRuntime
        return CreativeRuntime.create(allow_mock=allow_mock, production=not allow_mock).engine

    def _generate(self, task: dict[str, Any]) -> dict[str, Any]:
        requirement = dict(task.get("creative_requirement") or task.get("creative_brief") or {})
        for key in ("brief", "aspect_ratio", "duration_seconds", "face_visible", "character_id", "variant_count", "budget", "commerce_intent", "camera", "motion", "style", "workflow_id", "account_id", "series_id", "episode_id", "platform", "world_id", "creative_context", "normalized_prompt"):
            if key in task and key not in requirement:
                requirement[key] = task[key]
        context = task.get("creative_context") or requirement.get("creative_context")
        if context is not None and hasattr(context, "normalized_prompt"):
            requirement["creative_context"] = {
                "context_id": context.context_id,
                "normalized_prompt": context.normalized_prompt,
                "character_context": dict(context.character_context),
                "world_context": dict(context.world_context),
                "continuity_context": dict(context.continuity_context),
                "platform_context": dict(context.platform_context),
            }
            requirement.setdefault("brief", context.normalized_prompt or context.creative_request)
            requirement.setdefault("account_id", context.account_id)
            requirement.setdefault("series_id", context.series_id)
            requirement.setdefault("episode_id", context.episode_id)
            requirement.setdefault("platform", context.platform)
            requirement.setdefault("character_id", context.character_id)
            requirement.setdefault("world_id", context.world_id)
            requirement.setdefault("creative_context_id", context.context_id)
            aspect = (context.platform_context or {}).get("aspect_ratio")
            if aspect:
                requirement.setdefault("aspect_ratio", aspect)
        if task.get("title") and not requirement.get("brief"):
            requirement["brief"] = task.get("title")
        allow_mock = bool(task.get("allow_mock"))
        engine = self._engine(allow_mock=allow_mock)
        workflow = resolve_from_requirement(requirement)
        run = engine.execute(
            workflow.workflow_id,
            requirement,
            budget=requirement.get("budget"),
            idempotency_key=task.get("idempotency_key"),
            allow_mock=allow_mock if "allow_mock" in task else None,
        )
        assets = [engine.store.assets.get(item) or engine.store.get_asset(item) for item in run.asset_ids]
        package = None
        if run.status == "SUCCEEDED":
            package = engine.to_content_package(
                run,
                package_id=str(task.get("package_id") or f"pkg-{run.run_id[:8]}"),
                title=str(task.get("title") or requirement.get("brief") or "Untitled"),
                body=str(task.get("body") or requirement.get("brief") or ""),
                creative_context=task.get("creative_context"),
            )
        code = run.error_code or run.blocked_reason or ""
        if (run.status == "SUCCEEDED" or code in CREATIVE_MEMORY_CODES) and requirement.get("account_id"):
            write_patterns({
                "kind": "workflow",
                "account_id": requirement.get("account_id"),
                "platform": requirement.get("platform") or "",
                "series_id": requirement.get("series_id"),
                "episode_id": requirement.get("episode_id"),
                "successful_pattern" if run.status == "SUCCEEDED" else "failed_pattern": {
                    "workflow_id": run.workflow_id,
                    "workflow_version": run.workflow_version,
                    "status": run.status,
                    "error_code": code,
                    "character_id": requirement.get("character_id"),
                },
                "confidence": 0.6 if run.status == "SUCCEEDED" else 0.4,
            })
        error = run.blocked_message or run.error
        if run.status == "BLOCKED":
            error = f"Creative generation blocked: {error or run.blocked_reason or run.status}"
        return {
            "agent": self.name,
            "valid": run.status == "SUCCEEDED",
            "run": run,
            "workflow_id": run.workflow_id,
            "workflow_version": run.workflow_version,
            "assets": [item for item in assets if item],
            "package": package,
            "blocked": run.status == "BLOCKED",
            "blocked_reason": run.blocked_reason,
            "error": error,
        }

    def _hash_local(self, task: dict[str, Any]) -> dict[str, Any]:
        paths = [Path(item) for item in task.get("media") or task.get("media_assets") or []]
        missing = [str(path) for path in paths if not path.is_file()]
        ready = []
        for path in paths:
            if not path.is_file():
                continue
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            ready.append({
                "source_path": str(path),
                "source_hash": digest.hexdigest(),
                "size": path.stat().st_size,
                "mime_type": None,
            })
        return {
            "agent": self.name,
            "valid": not missing,
            "missing": missing,
            "ready": ready,
        }
