"""PostgreSQL is the production source of truth for creative runtime state."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine, or_, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from creative.assets import AssetStore, character_from_dict
from creative.errors import SchemaNotReady
from creative.schemas import (
    Character,
    CreativeRun,
    CreativeTask,
    GenerationUsage,
    JudgeResult,
    MediaAsset,
    PromptAsset,
    VisualDNA,
    WorkflowPerformance,
    to_plain,
    utcnow,
)

CREATIVE_TABLE_NAMES = (
    "creative_workflows",
    "creative_runs",
    "creative_tasks",
    "creative_node_outputs",
    "media_assets",
    "characters",
    "prompt_assets",
    "generation_usage",
    "workflow_performance",
    "judge_results",
    "creative_events",
)

LEASE_SECONDS = 30
OPEN_TASK_STATES = {"QUEUED", "RUNNING"}
RECOVERABLE_RUN_STATES = ("WAITING_PROVIDER", "QUEUED", "RUNNING", "JUDGING")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed


def _iso(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _num(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _json(value: Any, default: Any) -> Any:
    return default if value is None else value


def is_test_runtime() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or os.environ.get("MEITI_CREATIVE_STORE") == "memory"


def sqlite_engine(url: str | None = None):
    connect_args = {"check_same_thread": False}
    if url and url != "sqlite://":
        return create_engine(url, connect_args=connect_args)
    return create_engine("sqlite://", connect_args=connect_args, poolclass=StaticPool)


def production_engine():
    from scripts.db.engine import engine
    return engine


def schema_ready(engine) -> tuple[bool, list[str]]:
    from sqlalchemy import inspect

    existing = set(inspect(engine).get_table_names())
    missing = [name for name in CREATIVE_TABLE_NAMES if name not in existing]
    return (not missing, missing)


def ensure_creative_schema(engine, *, allow_create: bool = False) -> None:
    from scripts.db.models import Base

    ready, missing = schema_ready(engine)
    if ready:
        return
    if not allow_create:
        raise SchemaNotReady("creative schema missing: " + ", ".join(missing))
    tables = [Base.metadata.tables[name] for name in CREATIVE_TABLE_NAMES if name in Base.metadata.tables]
    Base.metadata.create_all(engine, tables=tables)


class CreativeStore:
    def __init__(self, *, assets: AssetStore | None = None, engine=None, lease_seconds: int = LEASE_SECONDS) -> None:
        self.assets = assets or AssetStore()
        self.lease_seconds = lease_seconds
        if engine is None:
            engine = sqlite_engine() if is_test_runtime() else production_engine()
        self.engine = engine
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        dialect = getattr(getattr(self.engine, "dialect", None), "name", "")
        allow_create = is_test_runtime() or dialect == "sqlite"
        ensure_creative_schema(self.engine, allow_create=allow_create)
        self.assets._persist_asset = self.save_asset
        self.assets._persist_character = self.save_character
        self.assets._load_character = self.get_character
        self._hydrate_assets()

    @classmethod
    def production(cls, *, assets: AssetStore | None = None) -> "CreativeStore":
        store = cls.__new__(cls)
        store.assets = assets or AssetStore()
        store.lease_seconds = LEASE_SECONDS
        store.engine = production_engine()
        store.Session = sessionmaker(autocommit=False, autoflush=False, bind=store.engine)
        ensure_creative_schema(store.engine, allow_create=False)
        store.assets._persist_asset = store.save_asset
        store.assets._persist_character = store.save_character
        store.assets._load_character = store.get_character
        store._hydrate_assets()
        return store

    def _session(self):
        return self.Session()

    def _hydrate_assets(self) -> None:
        from scripts.db.models import MediaAssetRecord, CharacterRecord

        try:
            with self._session() as session:
                for row in session.execute(select(MediaAssetRecord)).scalars():
                    self.assets.put(_asset_from_row(row), persist=False)
                for row in session.execute(select(CharacterRecord)).scalars():
                    self.assets.characters[row.character_id] = _character_from_row(row)
        except Exception:
            return

    def save_run(self, run: CreativeRun) -> CreativeRun:
        from scripts.db.models import CreativeRunRecord

        payload = _run_row(run)
        with self._session() as session:
            existing = session.get(CreativeRunRecord, run.run_id)
            if existing is None:
                session.add(CreativeRunRecord(**payload))
            else:
                for key, value in payload.items():
                    setattr(existing, key, value)
            session.commit()
        return run

    def get_run(self, run_id: str) -> CreativeRun | None:
        from scripts.db.models import CreativeRunRecord

        with self._session() as session:
            row = session.get(CreativeRunRecord, run_id)
            return _run_from_row(row) if row else None

    def get_by_idempotency(self, key: str) -> CreativeRun | None:
        from scripts.db.models import CreativeRunRecord

        if not key:
            return None
        with self._session() as session:
            row = session.execute(select(CreativeRunRecord).where(CreativeRunRecord.idempotency_key == key)).scalar_one_or_none()
            return _run_from_row(row) if row else None

    def save_task(self, task: CreativeTask) -> None:
        from scripts.db.models import CreativeTaskRecord

        payload = _task_row(task)
        with self._session() as session:
            existing = session.get(CreativeTaskRecord, task.task_id)
            if existing is None:
                session.add(CreativeTaskRecord(**payload))
            else:
                for key, value in payload.items():
                    setattr(existing, key, value)
            session.commit()

    def get_task(self, task_id: str) -> CreativeTask | None:
        from scripts.db.models import CreativeTaskRecord

        with self._session() as session:
            row = session.get(CreativeTaskRecord, task_id)
            return _task_from_row(row) if row else None

    def list_open_tasks(self, run_id: str) -> list[CreativeTask]:
        from scripts.db.models import CreativeTaskRecord

        with self._session() as session:
            rows = session.execute(
                select(CreativeTaskRecord).where(
                    CreativeTaskRecord.run_id == run_id,
                    CreativeTaskRecord.status.in_(tuple(OPEN_TASK_STATES)),
                )
            ).scalars()
            return [_task_from_row(row) for row in rows]

    def list_tasks(self, run_id: str) -> list[CreativeTask]:
        from scripts.db.models import CreativeTaskRecord

        with self._session() as session:
            rows = session.execute(select(CreativeTaskRecord).where(CreativeTaskRecord.run_id == run_id)).scalars()
            return [_task_from_row(row) for row in rows]

    def get_task_by_execution_key(self, execution_key: str) -> CreativeTask | None:
        from scripts.db.models import CreativeTaskRecord

        with self._session() as session:
            row = session.execute(select(CreativeTaskRecord).where(CreativeTaskRecord.execution_key == execution_key)).scalar_one_or_none()
            return _task_from_row(row) if row else None

    def save_usage(self, usage: GenerationUsage) -> None:
        from scripts.db.models import GenerationUsageRecord

        with self._session() as session:
            existing = session.get(GenerationUsageRecord, usage.usage_id)
            payload = {
                "usage_id": usage.usage_id,
                "provider": usage.provider,
                "model": usage.model,
                "task": usage.task,
                "input": to_plain(usage.input),
                "output": to_plain(usage.output),
                "credits_estimated": usage.credits_estimated,
                "credits_actual": usage.credits_actual,
                "status": usage.status,
                "timestamp": _parse_dt(usage.timestamp) or _now(),
                "run_id": usage.run_id,
                "node_id": usage.node_id,
                "input_units": getattr(usage, "input_units", 0.0) or 0.0,
                "output_units": getattr(usage, "output_units", 0.0) or 0.0,
                "duration_ms": getattr(usage, "duration_ms", 0.0) or 0.0,
                "estimated_cost": getattr(usage, "estimated_cost", None) if getattr(usage, "estimated_cost", 0) else usage.credits_estimated,
                "actual_cost": getattr(usage, "actual_cost", None) if getattr(usage, "actual_cost", 0) else usage.credits_actual,
            }
            if existing is None:
                session.add(GenerationUsageRecord(**payload))
            else:
                for key, value in payload.items():
                    setattr(existing, key, value)
            session.commit()

    def save_prompt(self, prompt: PromptAsset) -> None:
        from scripts.db.models import PromptAssetRecord

        with self._session() as session:
            existing = session.get(PromptAssetRecord, prompt.prompt_id)
            payload = {
                "prompt_id": prompt.prompt_id,
                "version": prompt.version,
                "family_id": prompt.family_id or prompt.prompt_id,
                "prompt": prompt.prompt,
                "negative_prompt": prompt.negative_prompt,
                "references": list(prompt.references),
                "model": prompt.model,
                "provider": prompt.provider,
                "parameters": dict(prompt.parameters or {}),
                "workflow_id": prompt.workflow_id,
                "workflow_version": prompt.workflow_version,
            }
            if existing is None:
                session.add(PromptAssetRecord(**payload))
            else:
                for key, value in payload.items():
                    setattr(existing, key, value)
            session.commit()

    def list_runs(self, status: str | None = None) -> list[CreativeRun]:
        from scripts.db.models import CreativeRunRecord

        with self._session() as session:
            stmt = select(CreativeRunRecord)
            if status:
                stmt = stmt.where(CreativeRunRecord.status == status)
            return [_run_from_row(row) for row in session.execute(stmt).scalars()]

    def list_recoverable_runs(self) -> list[CreativeRun]:
        from scripts.db.models import CreativeRunRecord

        with self._session() as session:
            rows = session.execute(
                select(CreativeRunRecord).where(CreativeRunRecord.status.in_(RECOVERABLE_RUN_STATES))
            ).scalars()
            return [_run_from_row(row) for row in rows]

    def acquire_lease(self, run_id: str, worker_id: str, *, seconds: int | None = None) -> bool:
        from scripts.db.models import CreativeRunRecord

        ttl = int(seconds if seconds is not None else self.lease_seconds)
        now = _now()
        with self._session() as session:
            result = session.execute(
                update(CreativeRunRecord)
                .where(CreativeRunRecord.run_id == run_id)
                .where(
                    or_(
                        CreativeRunRecord.worker_id.is_(None),
                        CreativeRunRecord.worker_id == "",
                        CreativeRunRecord.worker_id == worker_id,
                        CreativeRunRecord.lease_until.is_(None),
                        CreativeRunRecord.lease_until < now,
                    )
                )
                .values(worker_id=worker_id, lease_until=now + timedelta(seconds=ttl), heartbeat_at=now)
            )
            session.commit()
            return int(result.rowcount or 0) == 1

    def heartbeat(self, run_id: str, worker_id: str, *, seconds: int | None = None) -> bool:
        return self.acquire_lease(run_id, worker_id, seconds=seconds)

    def release_lease(self, run_id: str, worker_id: str | None = None) -> None:
        from scripts.db.models import CreativeRunRecord

        with self._session() as session:
            row = session.get(CreativeRunRecord, run_id)
            if row is None:
                return
            if worker_id and row.worker_id not in {None, "", worker_id}:
                return
            row.worker_id = None
            row.lease_until = None
            session.commit()

    def save_node_output(self, run_id: str, node_id: str, output: dict[str, Any], assets: list[Any] | None = None) -> None:
        from scripts.db.models import CreativeNodeOutputRecord

        payload = to_plain(output)
        asset_ids = []
        for item in assets or []:
            if isinstance(item, MediaAsset):
                asset_ids.append(item.asset_id)
            elif isinstance(item, dict) and item.get("asset_id"):
                asset_ids.append(item["asset_id"])
            elif isinstance(item, str):
                asset_ids.append(item)
        with self._session() as session:
            existing = session.execute(
                select(CreativeNodeOutputRecord).where(
                    CreativeNodeOutputRecord.run_id == run_id,
                    CreativeNodeOutputRecord.node_id == node_id,
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(CreativeNodeOutputRecord(run_id=run_id, node_id=node_id, output=payload, assets=asset_ids, timestamp=_now()))
            else:
                existing.output = payload
                existing.assets = asset_ids
                existing.timestamp = _now()
            session.commit()

    def save_asset(self, asset: MediaAsset) -> MediaAsset:
        from scripts.db.models import MediaAssetRecord

        payload = {
            "asset_id": asset.asset_id,
            "sha256": asset.sha256,
            "type": asset.type,
            "path": asset.path,
            "mime_type": asset.mime_type,
            "size": asset.size,
            "width": asset.width,
            "height": asset.height,
            "duration": asset.duration,
            "fps": asset.fps,
            "workflow_id": asset.workflow_id,
            "workflow_version": asset.workflow_version,
            "creative_run_id": asset.creative_run_id,
            "prompt_id": asset.prompt_id,
            "character_id": asset.character_id,
            "metadata_json": dict(asset.metadata or {}),
            "account_id": getattr(asset, "account_id", None),
            "series_id": getattr(asset, "series_id", None),
            "episode_id": getattr(asset, "episode_id", None),
            "content_package_id": getattr(asset, "content_package_id", None),
            "creative_context_id": getattr(asset, "creative_context_id", None),
            "world_id": getattr(asset, "world_id", None),
            "provider": getattr(asset, "provider", "") or "",
            "provider_task_id": getattr(asset, "provider_task_id", "") or "",
            "model": getattr(asset, "model", "") or "",
            "technical_score": asset.technical_score,
            "visual_score": asset.visual_score,
            "content_score": asset.content_score,
            "platform_score": asset.platform_score,
            "overall_score": asset.overall_score,
        }
        with self._session() as session:
            by_hash = session.execute(select(MediaAssetRecord).where(MediaAssetRecord.sha256 == asset.sha256)).scalar_one_or_none()
            existing = by_hash or session.get(MediaAssetRecord, asset.asset_id)
            if existing is None:
                session.add(MediaAssetRecord(**payload))
                session.commit()
                return asset
            return _asset_from_row(existing)

    def get_asset(self, asset_id: str) -> MediaAsset | None:
        cached = self.assets.get(asset_id)
        if cached:
            return cached
        from scripts.db.models import MediaAssetRecord

        with self._session() as session:
            row = session.get(MediaAssetRecord, asset_id)
            if row is None:
                row = session.execute(select(MediaAssetRecord).where(MediaAssetRecord.sha256 == asset_id)).scalar_one_or_none()
            if row is None:
                return None
            asset = _asset_from_row(row)
            self.assets.put(asset, persist=False)
            return asset

    def list_assets(self, run_id: str | None = None) -> list[MediaAsset]:
        from scripts.db.models import MediaAssetRecord

        with self._session() as session:
            stmt = select(MediaAssetRecord)
            if run_id:
                stmt = stmt.where(MediaAssetRecord.creative_run_id == run_id)
            return [_asset_from_row(row) for row in session.execute(stmt).scalars()]

    def save_character(self, character: Character) -> Character:
        from scripts.db.models import CharacterRecord

        payload = {
            "character_id": character.character_id,
            "name": character.name,
            "visual_dna": to_plain(character.visual_dna),
            "behavior_dna": character.behavior_dna,
            "style_dna": character.style_dna,
            "reference_assets": list(character.reference_assets),
            "voice_assets": list(character.voice_assets),
            "notes": character.notes,
            "updated_at": _now(),
        }
        with self._session() as session:
            existing = session.get(CharacterRecord, character.character_id)
            if existing is None:
                session.add(CharacterRecord(**payload))
            else:
                for key, value in payload.items():
                    setattr(existing, key, value)
            session.commit()
        self.assets.characters[character.character_id] = character
        return character

    def get_character(self, character_id: str) -> Character | None:
        cached = self.assets.characters.get(character_id)
        if cached:
            return cached
        from scripts.db.models import CharacterRecord

        with self._session() as session:
            row = session.get(CharacterRecord, character_id)
            if row is None:
                return None
            character = _character_from_row(row)
            self.assets.characters[character_id] = character
            return character

    def save_judge_result(self, result: JudgeResult | dict[str, Any], *, run_id: str = "") -> None:
        from scripts.db.models import JudgeResultRecord
        from uuid import uuid4

        payload = to_plain(result) if not isinstance(result, dict) else dict(result)
        judge_id = str(payload.get("judge_id") or uuid4().hex)
        with self._session() as session:
            session.add(JudgeResultRecord(
                judge_id=judge_id,
                asset_id=payload.get("asset_id"),
                creative_run_id=str(payload.get("creative_run_id") or run_id or ""),
                judge_type=str(payload.get("judge_type") or ""),
                judge_provider=str(payload.get("judge_provider") or ""),
                judge_model=str(payload.get("judge_model") or ""),
                judge_version=str(payload.get("judge_version") or ""),
                score=_num(payload.get("score")),
                breakdown=dict(payload.get("breakdown") or {}),
                reasons=list(payload.get("reasons") or []),
                decision=str(payload.get("decision") or ""),
                timestamp=_parse_dt(payload.get("timestamp")) or _now(),
            ))
            session.commit()

    def save_performance(self, item: WorkflowPerformance | dict[str, Any]) -> None:
        from scripts.db.models import WorkflowPerformanceRecord

        payload = to_plain(item) if not isinstance(item, dict) else dict(item)
        with self._session() as session:
            session.add(WorkflowPerformanceRecord(
                workflow_id=str(payload.get("workflow_id") or ""),
                version=str(payload.get("version") or ""),
                run_id=str(payload.get("run_id") or ""),
                asset_id=str(payload.get("asset_id") or ""),
                publication_id=str(payload.get("publication_id") or ""),
                platform=str(payload.get("platform") or ""),
                provider=str(payload.get("provider") or ""),
                model=str(payload.get("model") or ""),
                character=str(payload.get("character") or ""),
                scene=str(payload.get("scene") or ""),
                motion=str(payload.get("motion") or ""),
                camera=str(payload.get("camera") or ""),
                duration=payload.get("duration"),
                quality_score=payload.get("quality_score"),
                engagement=payload.get("engagement"),
                conversion=payload.get("conversion"),
                cost=payload.get("cost"),
                latency=payload.get("latency"),
            ))
            session.commit()

    def list_performance(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        from scripts.db.models import WorkflowPerformanceRecord

        with self._session() as session:
            stmt = select(WorkflowPerformanceRecord)
            if workflow_id:
                stmt = stmt.where(WorkflowPerformanceRecord.workflow_id == workflow_id)
            rows = []
            for row in session.execute(stmt).scalars():
                rows.append({
                    "workflow_id": row.workflow_id,
                    "version": row.version,
                    "run_id": row.run_id,
                    "quality_score": _num(row.quality_score, 0),
                    "engagement": _num(row.engagement, 0),
                    "cost": _num(row.cost, 0),
                    "latency": _num(row.latency, 0),
                    "provider": row.provider,
                    "model": row.model,
                    "character": row.character,
                })
            return rows

    def record_event(self, run_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        from scripts.db.models import CreativeEventRecord

        with self._session() as session:
            session.add(CreativeEventRecord(run_id=run_id, event_type=event_type, payload=dict(payload or {}), timestamp=_now()))
            session.commit()

    def save_workflow_snapshot(self, snapshot: dict[str, Any]) -> None:
        from scripts.db.models import CreativeWorkflowRecord

        workflow_id = str(snapshot.get("workflow_id") or "")
        version = str(snapshot.get("version") or "")
        if not workflow_id or not version:
            return
        payload = {
            "workflow_id": workflow_id,
            "version": version,
            "name": str(snapshot.get("name") or workflow_id),
            "description": str(snapshot.get("description") or ""),
            "category": str(snapshot.get("category") or "video"),
            "inputs": dict(snapshot.get("inputs") or {}),
            "nodes": list(snapshot.get("nodes") or []),
            "edges": list(snapshot.get("edges") or []),
            "variables": dict(snapshot.get("variables") or {}),
            "quality_policy": dict(snapshot.get("quality_policy") or {}),
            "outputs": dict(snapshot.get("outputs") or {}),
            "snapshot": snapshot,
            "updated_at": _now(),
        }
        with self._session() as session:
            existing = session.get(CreativeWorkflowRecord, (workflow_id, version))
            if existing is None:
                session.add(CreativeWorkflowRecord(**payload))
            else:
                from creative.errors import WorkflowInvalid
                current = existing.snapshot or {}
                if current and current != snapshot:
                    raise WorkflowInvalid(f"workflow version immutable: {workflow_id}@{version}")
            session.commit()

    def save_workflow_version(self, snapshot: dict[str, Any], *, source: str = "template") -> None:
        payload = dict(snapshot or {})
        payload.setdefault("source", source)
        self.save_workflow_snapshot(payload)

    def get_workflow_version(self, workflow_id: str, version: str) -> dict[str, Any] | None:
        from scripts.db.models import CreativeWorkflowRecord

        with self._session() as session:
            row = session.get(CreativeWorkflowRecord, (workflow_id, version))
            if row is None:
                return None
            return dict(row.snapshot or {})

    def list_workflow_versions(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        from scripts.db.models import CreativeWorkflowRecord

        with self._session() as session:
            stmt = select(CreativeWorkflowRecord)
            if workflow_id:
                stmt = stmt.where(CreativeWorkflowRecord.workflow_id == workflow_id)
            rows = []
            for row in session.execute(stmt).scalars():
                rows.append({
                    "workflow_id": row.workflow_id,
                    "version": row.version,
                    "name": row.name,
                    "snapshot": dict(row.snapshot or {}),
                    "source": str((row.snapshot or {}).get("source") or "template"),
                })
            return rows

    def list_workflow_definitions(self) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for item in self.list_workflow_versions():
            current = grouped.get(item["workflow_id"])
            if current is None or str(item["version"]) > str(current["latest_version"]):
                grouped[item["workflow_id"]] = {
                    "workflow_id": item["workflow_id"],
                    "name": item["name"],
                    "latest_version": item["version"],
                    "source": item["source"],
                }
        return list(grouped.values())


    def list_asset_references(self, asset_id: str) -> dict[str, list[str]]:
        from scripts.db.models import CreativeNodeOutputRecord, CreativeRunRecord, MediaAssetRecord, CharacterRecord

        refs: dict[str, list[str]] = {"runs": [], "node_outputs": [], "characters": [], "assets": [], "packages": [], "jobs": [], "memory": []}
        with self._session() as session:
            for row in session.execute(select(CreativeRunRecord)).scalars():
                ids = list(row.asset_ids or [])
                if asset_id in ids or row.selected_asset_id == asset_id:
                    refs["runs"].append(row.run_id)
            for row in session.execute(select(CreativeNodeOutputRecord)).scalars():
                ids = list(row.assets or [])
                output = row.output or {}
                if asset_id in ids or asset_id in list(output.get("asset_ids") or []):
                    refs["node_outputs"].append(f"{row.run_id}:{row.node_id}")
            for row in session.execute(select(CharacterRecord)).scalars():
                if asset_id in list(row.reference_assets or []) or asset_id in list(row.voice_assets or []):
                    refs["characters"].append(row.character_id)
            row = session.get(MediaAssetRecord, asset_id)
            if row is not None:
                refs["assets"].append(row.asset_id)
            try:
                from scripts.db.models import ContentPackageRecord, DistributionJobRecord
                for row in session.execute(select(ContentPackageRecord)).scalars():
                    media = list(row.media_assets or [])
                    meta = dict(row.metadata_json or {})
                    if asset_id in media or meta.get("selected_asset_id") == asset_id or any(asset_id in str(item) for item in media):
                        refs["packages"].append(row.package_id)
                for row in session.execute(select(DistributionJobRecord)).scalars():
                    variant = dict(row.variant or {})
                    media = list(variant.get("media") or variant.get("media_assets") or [])
                    if asset_id in media or any(asset_id in str(item) for item in media):
                        refs["jobs"].append(row.job_id)
            except Exception:
                pass
        return refs

    def delete_asset(self, asset_id: str, *, force: bool = False) -> bool:
        from scripts.db.models import MediaAssetRecord

        refs = self.list_asset_references(asset_id)
        live = [key for key, values in refs.items() if key != "assets" and values]
        if live and not force:
            return False
        asset = self.get_asset(asset_id)
        with self._session() as session:
            row = session.get(MediaAssetRecord, asset_id)
            if row is not None:
                session.delete(row)
                session.commit()
        if asset and getattr(asset, "path", None):
            from pathlib import Path
            path = Path(asset.path)
            # bytes stay if another run still points at the same sha path via remaining refs
            if not live and path.is_file():
                path.unlink()
        self.assets.assets.pop(asset_id, None)
        return True


class CharacterRepository:
    def __init__(self, store: CreativeStore) -> None:
        self.store = store

    def save(self, character: Character) -> Character:
        for ref in character.reference_assets:
            if ref and self.store.get_asset(str(ref)) is None and str(ref) not in self.store.assets.assets:
                raise ValueError(f"character reference is not a MediaAsset: {ref}")
        return self.store.save_character(character)

    def get(self, character_id: str) -> Character | None:
        return self.store.get_character(character_id)


def _run_row(run: CreativeRun) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "workflow_id": run.workflow_id,
        "workflow_version": run.workflow_version,
        "status": run.status,
        "inputs": dict(run.inputs or {}),
        "outputs": to_plain(run.outputs),
        "estimated_cost": run.estimated_cost,
        "actual_cost": run.actual_cost,
        "budget": run.budget,
        "idempotency_key": run.idempotency_key,
        "replay_of": run.replay_of,
        "cursor": run.cursor,
        "node_outputs": to_plain(run.node_outputs),
        "judge_results": to_plain(run.judge_results),
        "quality": dict(run.quality or {}),
        "error": run.error,
        "error_code": run.error_code,
        "workflow_snapshot": dict(run.workflow_snapshot or {}),
        "asset_ids": list(run.asset_ids or []),
        "task_ids": list(run.task_ids or []),
        "selected_asset_id": run.selected_asset_id,
        "selection_reason": run.selection_reason,
        "selection_score": run.selection_score,
        "worker_id": run.worker_id,
        "lease_until": _parse_dt(run.lease_until),
        "heartbeat_at": _parse_dt(run.heartbeat_at),
        "request_id": run.request_id or "",
        "started_at": _parse_dt(run.started_at),
        "completed_at": _parse_dt(run.completed_at),
        "blocked_reason": getattr(run, "blocked_reason", None),
        "blocked_message": getattr(run, "blocked_message", None),
        "blocked_at": _parse_dt(getattr(run, "blocked_at", None)),
        "retryable": bool(getattr(run, "retryable", False)),
        "updated_at": _now(),
    }


def _run_from_row(row) -> CreativeRun:
    return CreativeRun(
        run_id=row.run_id,
        workflow_id=row.workflow_id,
        workflow_version=row.workflow_version,
        status=row.status,
        inputs=_json(row.inputs, {}),
        outputs=_json(row.outputs, {}),
        estimated_cost=_num(row.estimated_cost),
        actual_cost=_num(row.actual_cost),
        budget=None if row.budget is None else _num(row.budget),
        idempotency_key=row.idempotency_key,
        replay_of=row.replay_of,
        cursor=int(row.cursor or 0),
        node_outputs=_json(row.node_outputs, {}),
        judge_results=_json(row.judge_results, []),
        quality=_json(row.quality, {}),
        error=row.error,
        error_code=row.error_code,
        workflow_snapshot=_json(row.workflow_snapshot, {}),
        asset_ids=list(_json(row.asset_ids, [])),
        task_ids=list(_json(row.task_ids, [])),
        selected_asset_id=row.selected_asset_id,
        selection_reason=row.selection_reason,
        selection_score=None if row.selection_score is None else _num(row.selection_score),
        worker_id=row.worker_id,
        lease_until=_iso(row.lease_until),
        heartbeat_at=_iso(row.heartbeat_at),
        request_id=row.request_id or "",
        started_at=_iso(row.started_at),
        completed_at=_iso(row.completed_at),
        blocked_reason=getattr(row, "blocked_reason", None),
        blocked_message=getattr(row, "blocked_message", None),
        blocked_at=_iso(getattr(row, "blocked_at", None)),
        retryable=bool(getattr(row, "retryable", False)),
    )


def _task_row(task: CreativeTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "run_id": task.run_id,
        "node_id": task.node_id,
        "provider": task.provider,
        "provider_task_id": task.provider_task_id or "",
        "kind": task.kind,
        "status": task.status,
        "payload": to_plain(task.payload),
        "result": to_plain(task.result),
        "poll_count": task.poll_count,
        "attempt": task.attempt,
        "execution_key": task.execution_key or f"{task.run_id}:{task.node_id}:{task.attempt}",
        "error": task.error,
        "started_at": _parse_dt(task.started_at),
        "completed_at": _parse_dt(task.completed_at),
        "timeout_at": _parse_dt(task.timeout_at),
    }


def _task_from_row(row) -> CreativeTask:
    return CreativeTask(
        task_id=row.task_id,
        run_id=row.run_id,
        node_id=row.node_id,
        provider=row.provider,
        provider_task_id=row.provider_task_id,
        kind=row.kind,
        status=row.status,
        payload=_json(row.payload, {}),
        result=_json(row.result, {}),
        poll_count=int(row.poll_count or 0),
        attempt=int(row.attempt or 0),
        execution_key=row.execution_key or "",
        error=row.error,
        started_at=_iso(row.started_at),
        completed_at=_iso(row.completed_at),
        timeout_at=_iso(row.timeout_at),
    )


def _asset_from_row(row) -> MediaAsset:
    return MediaAsset(
        asset_id=row.asset_id,
        type=row.type,
        path=row.path,
        sha256=row.sha256,
        width=row.width,
        height=row.height,
        duration=None if row.duration is None else _num(row.duration),
        fps=None if row.fps is None else _num(row.fps),
        mime_type=row.mime_type or "",
        workflow_id=row.workflow_id,
        workflow_version=row.workflow_version,
        creative_run_id=row.creative_run_id,
        prompt_id=row.prompt_id,
        character_id=row.character_id,
        size=int(row.size or 0),
        metadata=_json(row.metadata_json, {}),
        account_id=getattr(row, "account_id", None),
        series_id=getattr(row, "series_id", None),
        episode_id=getattr(row, "episode_id", None),
        content_package_id=getattr(row, "content_package_id", None),
        creative_context_id=getattr(row, "creative_context_id", None),
        world_id=getattr(row, "world_id", None),
        provider=getattr(row, "provider", "") or "",
        provider_task_id=getattr(row, "provider_task_id", "") or "",
        model=getattr(row, "model", "") or "",
        technical_score=None if row.technical_score is None else _num(row.technical_score),
        visual_score=None if row.visual_score is None else _num(row.visual_score),
        content_score=None if row.content_score is None else _num(row.content_score),
        platform_score=None if row.platform_score is None else _num(row.platform_score),
        overall_score=None if row.overall_score is None else _num(row.overall_score),
    )


def _character_from_row(row) -> Character:
    dna = _json(row.visual_dna, {})
    return Character(
        character_id=row.character_id,
        name=row.name,
        visual_dna=VisualDNA(**{key: str(dna.get(key) or "") for key in VisualDNA.__dataclass_fields__}),
        behavior_dna=row.behavior_dna or "",
        style_dna=row.style_dna or "",
        reference_assets=tuple(_json(row.reference_assets, [])),
        voice_assets=tuple(_json(row.voice_assets, [])),
        notes=row.notes or "",
    )
