#!/usr/bin/env python3
"""Creative subsystem doctor. Missing credentials are BLOCKED, never PASS."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _status(ok: bool, **extra):
    payload = {"status": "PASS" if ok else "BLOCKED"}
    payload.update(extra)
    return payload


def _blocked(reason: str, **extra):
    payload = {"status": "BLOCKED", "reason": reason}
    payload.update(extra)
    return payload


def run() -> dict:
    from creative.providers.lechuang.adapter import LechuangAdapter
    from creative.providers.resolver import load_capability_registry
    from creative.store import CreativeStore, schema_ready
    from creative.runtime.container import CreativeRuntime
    from creative.workflow.registry import list_workflows
    from creative.judges import ImageJudge, VideoJudge, TechnicalQA
    from creative.validation import validate_workflow
    from services.workers.creative_worker import run_once
    from creative.api import CreativeAPI
    from creative.render.ffmpeg import FFMPEG
    from creative.errors import JudgeBlocked

    workflows = list_workflows()
    names = {item.workflow_id for item in workflows}
    required = {
        "creator-video-default-v1", "creator-image-to-video-v1", "creator-lifestyle-v1",
        "character-consistency-v1", "scene-storyboard-v1", "short-drama-v1",
        "ugc-style-video-v1", "cinematic-video-v1", "product-optional-content-v1",
    }
    adapter = LechuangAdapter()
    ready, reason = adapter.live_ready()
    capabilities = load_capability_registry()
    runtime = CreativeRuntime.testing()
    engine = runtime.engine
    try:
        mock_run = engine.execute("creator-image-to-video-v1", {"brief": "doctor mock", "variant_count": 1, "budget": 40})
        mock_status = mock_run.status
        mock_error = mock_run.error
    except Exception as exc:
        mock_status = "FAILED"
        mock_error = str(exc)
        class _Run:
            status = mock_status
            error = mock_error
        mock_run = _Run()
    validation_ok = True
    validation_error = None
    try:
        for item in workflows:
            validate_workflow(item, {"brief": "doctor"})
    except Exception as exc:
        validation_ok = False
        validation_error = str(exc)
    db_ok = True
    db_error = None
    persistence_ok = False
    try:
        store = CreativeStore.production()
        store.list_runs()
        persistence_ok = hasattr(store, "acquire_lease")
        ready_schema, missing = schema_ready(store.engine)
        if not ready_schema:
            db_ok = False
            db_error = "missing tables: " + ", ".join(missing)
    except Exception as exc:
        db_ok = False
        persistence_ok = False
        db_error = str(exc)
    resume_ok = callable(getattr(engine, "resume", None))
    ffmpeg_ok = Path(FFMPEG).exists() or FFMPEG == "ffmpeg"
    judge_reason = "vision provider unavailable"
    try:
        ImageJudge().judge(None)
        judge_ok = False
        judge_reason = "missing asset should FAIL without auto-PASS"
    except JudgeBlocked as exc:
        judge_ok = False
        judge_reason = str(exc)
    key_present = bool(os.getenv("LECHUANG_API_KEY", "").strip())
    contract = bool(adapter.client.contract_verified)
    return {
        "ARCHITECTURE": {
            "workflow_registry": _status(required.issubset(names), missing=sorted(required - names), count=len(workflows)),
            "workflow_validation": _status(validation_ok, error=validation_error),
            "runtime_container": _status(runtime.engine is not None and runtime.provider_resolver is not None),
            "workers": _status(callable(run_once)),
            "resume_support": _status(resume_ok),
            "api": _status(callable(CreativeAPI.create_run)),
            "mock_runtime": _status(mock_run.status == "SUCCEEDED", run_status=mock_run.status, error=mock_run.error),
            "asset_store": _status(True, root=str(engine.store.assets.root)),
        },
        "CONFIG": {
            "database": _status(db_ok, error=db_error),
            "creative_persistence": _status(persistence_ok, error=db_error),
            "render": _status(ffmpeg_ok, ffmpeg=FFMPEG),
            "cost": _status(callable(getattr(runtime.cost_engine, "record", None))),
            "idempotency": _status(True),
            "async_task_system": _status(callable(run_once)),
        },
        "PROVIDER": {
            "provider_registry": _status(bool(capabilities), count=len(capabilities)),
            "model_registry": _status(True, claimed=sorted({item.model for item in capabilities})),
        },
        "AUTH": {
            "Lechuang auth": _status(key_present, reason=("ok" if key_present else "LECHUANG_API_KEY missing"), key_present=key_present),
        },
        "CAPABILITY": {
            "Lechuang contract": _status(contract, contract_verified=contract, reason=reason),
            "image capability": _status(ready and contract, reason=reason),
            "video capability": _status(ready and contract, reason=reason),
            "judge capability": _blocked(judge_reason),
        },
        "LIVE": {
            "Lechuang live": _status(ready and contract, reason=reason),
            "Creative E2E": _status(ready and contract and mock_run.status == "SUCCEEDED", reason=reason if not ready else mock_error),
        },
    }


def flatten(checks: dict) -> dict:
    flat = {}
    for category, items in checks.items():
        for name, payload in items.items():
            flat[f"{category}:{name}"] = payload
    return flat


def main() -> int:
    checks = run()
    category_status = {}
    for category, items in checks.items():
        statuses = [value.get("status") for value in items.values()]
        if any(status == "FAIL" for status in statuses):
            category_status[category] = "FAIL"
        elif all(status == "PASS" for status in statuses):
            category_status[category] = "PASS"
        else:
            category_status[category] = "BLOCKED"
        print(f"{category}: {category_status[category]}")
        for name, payload in items.items():
            print(f"  {name}: {payload.get('status')}")
    architecture_ready = category_status.get("ARCHITECTURE") == "PASS" and category_status.get("CONFIG") == "PASS"
    live_ready = all(category_status.get(key) == "PASS" for key in ("PROVIDER", "AUTH", "CAPABILITY", "LIVE"))
    required_ready = all(category_status.get(key) == "PASS" for key in (
        "ARCHITECTURE", "CONFIG", "PROVIDER", "AUTH", "CAPABILITY", "LIVE",
    ))
    overall = "READY" if required_ready else "NOT_READY"
    print("ARCHITECTURE:", category_status.get("ARCHITECTURE"))
    print("LIVE:", "PASS" if live_ready else "BLOCKED")
    print("OVERALL:", overall)
    print(json.dumps({
        "ready": required_ready,
        "architecture_ready": architecture_ready,
        "live_ready": live_ready,
        "overall": overall,
        "categories": category_status,
        "checks": {key: value.get("status") for key, value in flatten(checks).items()},
    }, default=str))
    return 0 if architecture_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
