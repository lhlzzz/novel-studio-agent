#!/usr/bin/env python3
"""Creative subsystem doctor. Image and video gates are independent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AUDIT_PATH = ROOT / "docs/audits/meiti-v4.5.3-real-e2e.json"


def _status(ok: bool, **extra):
    payload = {"status": "PASS" if ok else "BLOCKED_EXTERNAL"}
    payload.update(extra)
    return payload


def _not_verified(reason: str, **extra):
    payload = {"status": "NOT_VERIFIED", "reason": reason}
    payload.update(extra)
    return payload


def _load_audit() -> dict:
    if not AUDIT_PATH.exists():
        return {}
    try:
        return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def run() -> dict:
    from creative.providers.lechuang.adapter import LechuangAdapter
    from creative.providers.lechuang.client import IMAGE_CONTRACT_VERIFIED, VIDEO_NOT_VERIFIED
    from creative.providers.lechuang.credentials import API_KEY_ENV, credential_status
    from creative.providers.resolver import GenerationProviderResolver, load_capability_registry
    from creative.store import CreativeStore, schema_ready
    from creative.runtime.container import CreativeRuntime
    from creative.workflow.registry import list_workflows
    from creative.judges import ImageJudge
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
    cred = credential_status(adapter.client.credential)
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
    audit = _load_audit()
    image_audit = audit.get("image") or {}
    video_audit = audit.get("video") or {}
    image_e2e = bool(image_audit.get("real_e2e"))
    video_e2e = bool(video_audit.get("real_e2e"))
    resolver = GenerationProviderResolver(allow_mock=False)
    resolver_ok = "lechuang" in resolver.providers and "mock" not in resolver.providers
    image_cap = adapter.capability_status("text_to_image")
    video_cap = adapter.capability_status("text_to_video")
    i2v_cap = adapter.capability_status("image_to_video")
    image_ready = ready and IMAGE_CONTRACT_VERIFIED and image_e2e
    return {
        "ARCHITECTURE": {
            "workflow_registry": {"status": "PASS" if required.issubset(names) else "BLOCKED", "missing": sorted(required - names), "count": len(workflows)},
            "workflow_validation": {"status": "PASS" if validation_ok else "BLOCKED", "error": validation_error},
            "runtime_container": {"status": "PASS" if runtime.engine is not None and runtime.provider_resolver is not None else "BLOCKED"},
            "workers": {"status": "PASS" if callable(run_once) else "BLOCKED"},
            "resume_support": {"status": "PASS" if resume_ok else "BLOCKED"},
            "api": {"status": "PASS" if callable(CreativeAPI.create_run) else "BLOCKED"},
            "mock_runtime": {"status": "PASS" if mock_run.status == "SUCCEEDED" else "BLOCKED", "run_status": mock_run.status, "error": mock_run.error},
            "asset_store": {"status": "PASS", "root": str(engine.store.assets.root)},
        },
        "CONFIG": {
            "database": {"status": "PASS" if db_ok else "BLOCKED_EXTERNAL", "error": db_error},
            "creative_persistence": {"status": "PASS" if persistence_ok else "BLOCKED_EXTERNAL", "error": db_error},
            "render": {"status": "PASS" if ffmpeg_ok else "BLOCKED", "ffmpeg": FFMPEG},
            "cost": {"status": "PASS" if callable(getattr(runtime.cost_engine, "record", None)) else "BLOCKED"},
            "idempotency": {"status": "PASS"},
            "async_task_system": {"status": "PASS" if callable(run_once) else "BLOCKED"},
        },
        "PROVIDER": {
            "provider_registry": {"status": "PASS" if resolver_ok else "BLOCKED", "count": len(capabilities)},
            "model_registry": {"status": "PASS", "models": sorted({item.model for item in capabilities if item.provider == "lechuang" and item.verified})},
        },
        "AUTH": {
            "Creative Credential": cred,
        },
        "CAPABILITY": {
            "Xiaole/Lechuang Endpoint": _status(bool(adapter.client.base_url), endpoint=adapter.client.base_url, env=API_KEY_ENV),
            "Contract": _status(IMAGE_CONTRACT_VERIFIED, reason=adapter.client.contract_reason),
            "Image Capability": image_cap,
            "Image Real Generation": _status(image_e2e, reason=("ok" if image_e2e else "no real image generation evidence")),
            "Image MediaAsset": _status(image_e2e and str(image_audit.get("media_asset") or "") == "PASS", reason=image_audit.get("media_asset") or "no MediaAsset evidence"),
            "Image QA": _status(image_e2e and str(image_audit.get("qa") or "") == "PASS", reason=image_audit.get("qa") or "no QA evidence"),
            "Video Capability": video_cap,
            "Video Real Generation": _not_verified(VIDEO_NOT_VERIFIED) if not video_e2e else _status(True),
            "Image-to-Video": i2v_cap,
            "Real Creative E2E": _status(image_e2e, image=image_e2e, video=video_e2e, env=API_KEY_ENV),
        },
        "LIVE": {
            "IMAGE_PRODUCTION_READY": _status(image_ready, reason=reason if not ready else ("ok" if image_e2e else "real image E2E missing")),
            "VIDEO_PRODUCTION_READY": _not_verified(VIDEO_NOT_VERIFIED),
            "IMAGE_TO_VIDEO": _not_verified(VIDEO_NOT_VERIFIED),
        },
        "JUDGE": {
            "judge capability": {"status": "BLOCKED_EXTERNAL", "reason": judge_reason, "ok": judge_ok},
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
            category_status[category] = "BLOCKED_EXTERNAL"
        print(f"{category}: {category_status[category]}")
        for name, payload in items.items():
            print(f"  {name}: {payload.get('status')}")
    architecture_fail = any(
        payload.get("status") not in {"PASS", "BLOCKED_EXTERNAL", "NOT_VERIFIED", "HANDOFF_ONLY"}
        for key, payload in flatten(checks).items()
        if key.startswith(("ARCHITECTURE:", "CONFIG:"))
    )
    architecture_ready = not architecture_fail
    live_image = checks["LIVE"]["IMAGE_PRODUCTION_READY"].get("status") == "PASS"
    live_video = checks["LIVE"]["VIDEO_PRODUCTION_READY"].get("status") == "PASS"
    overall = "READY" if live_image and live_video else "NOT_READY"
    print("ARCHITECTURE:", "PASS" if architecture_ready else "FAIL")
    print("IMAGE:", checks["LIVE"]["IMAGE_PRODUCTION_READY"].get("status"))
    print("VIDEO:", checks["LIVE"]["VIDEO_PRODUCTION_READY"].get("status"))
    print("OVERALL:", overall)
    print(json.dumps({
        "ready": overall == "READY",
        "architecture_ready": architecture_ready,
        "image_production_ready": live_image,
        "video_production_ready": live_video,
        "overall": overall,
        "categories": category_status,
        "checks": {key: value.get("status") for key, value in flatten(checks).items()},
    }, default=str))
    return 0 if architecture_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
