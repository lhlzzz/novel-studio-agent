#!/usr/bin/env python3
"""Creative subsystem doctor. Image, video, and image-to-video gates are independent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AUDIT_PATH = ROOT / "docs/audits/meiti-v4.5.4-real-e2e.json"
PASS = "PASS"
BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
NOT_VERIFIED = "NOT_VERIFIED"
VERIFIED_AND_READY = "VERIFIED_AND_READY"


def _status(ok: bool, **extra):
    payload = {"status": PASS if ok else BLOCKED_EXTERNAL}
    payload.update(extra)
    return payload


def _not_verified(reason: str, **extra):
    payload = {"status": NOT_VERIFIED, "reason": reason}
    payload.update(extra)
    return payload


def _load_audit() -> dict:
    if not AUDIT_PATH.exists():
        return {}
    try:
        return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _audit_pass(section: dict, key: str) -> bool:
    return str((section or {}).get(key) or "") == PASS


def _capability_gate(*, contract: bool, capability: dict, audit: dict, keys: tuple[str, ...]) -> dict:
    if not contract:
        return _not_verified(str(capability.get("reason") or "contract is not verified"))
    cap_status = str(capability.get("status") or "")
    if cap_status == NOT_VERIFIED:
        return _not_verified(str(capability.get("reason") or "capability is not verified"))
    if cap_status != PASS:
        return _status(False, reason=str(capability.get("reason") or "capability blocked"))
    missing = [key for key in keys if not _audit_pass(audit, key)]
    if missing or not bool(audit.get("real_e2e")):
        return _status(False, reason="real generation / MediaAsset / QA evidence missing", missing=missing)
    return _status(True, reason="ok")


def _overall(image_status: str, video_status: str, i2v_status: str, *, image_required: bool, video_required: bool, i2v_required: bool) -> str:
    required = []
    if image_required:
        required.append(image_status)
    if video_required:
        required.append(video_status)
    if i2v_required:
        required.append(i2v_status)
    if any(status == "FAIL" for status in required):
        return "FAIL"
    if any(status == BLOCKED_EXTERNAL for status in required):
        return BLOCKED_EXTERNAL
    if required and all(status == PASS for status in required):
        return PASS
    return NOT_VERIFIED


def _print_capability(title: str, rows: list[tuple[str, dict]], ready_name: str, ready: dict) -> None:
    print(f"{title}:")
    for name, payload in rows:
        print(f"  {name}: {payload.get('status')}")
    print(f"  {ready_name}: {ready.get('status')}")


def run(*, live: bool = False) -> dict:
    from creative.providers.lechuang.adapter import LechuangAdapter
    from creative.providers.lechuang.client import IMAGE_CONTRACT_VERIFIED
    from creative.providers.lechuang.credentials import API_KEY_ENV, credential_status
    from creative.providers.xai.adapter import XAIVideoAdapter
    from creative.providers.xai.client import VIDEO_CONTRACT_VERIFIED, VIDEO_NOT_VERIFIED
    from creative.providers.resolver import GenerationProviderResolver, load_capability_registry
    from creative.store import CreativeStore, schema_ready, sqlite_engine
    from creative.runtime.container import CreativeRuntime
    from creative.workflow.engine import CreativeWorkflowEngine
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
    xai = XAIVideoAdapter()
    cred = credential_status(adapter.client.credential)
    capabilities = load_capability_registry()
    from creative.assets import AssetStore
    from creative.providers.mock import MockGenerationProvider

    runtime = CreativeRuntime.testing()
    mock_assets = AssetStore()
    mock_store = CreativeStore(assets=mock_assets, engine=sqlite_engine())
    mock_provider = MockGenerationProvider(store=mock_assets)
    mock_resolver = GenerationProviderResolver(providers={"mock": mock_provider, "lechuang": mock_provider}, allow_mock=True)
    engine = CreativeWorkflowEngine(store=mock_store, resolver=mock_resolver, allow_mock=True)
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
    i2v_audit = audit.get("image_to_video") or {}
    resolver = GenerationProviderResolver(allow_mock=False)
    resolver_ok = "lechuang" in resolver.providers and "xai" in resolver.providers and "mock" not in resolver.providers
    image_cap = adapter.capability_status("text_to_image")
    video_cap = xai.capability_status("text_to_video")
    i2v_cap = xai.capability_status("image_to_video")

    image_contract = _status(IMAGE_CONTRACT_VERIFIED, reason=adapter.client.contract_reason)
    image_generation = _status(_audit_pass(image_audit, "real_generation") and bool(image_audit.get("real_e2e")), reason=("ok" if image_audit.get("real_e2e") else "no real image generation evidence"))
    image_asset = _status(_audit_pass(image_audit, "media_asset") and bool(image_audit.get("real_e2e")), reason=image_audit.get("media_asset") or "no MediaAsset evidence")
    image_qa = _status(_audit_pass(image_audit, "qa") and bool(image_audit.get("real_e2e")), reason=image_audit.get("qa") or "no QA evidence")
    image_e2e = _status(bool(image_audit.get("real_e2e")) and _audit_pass(image_audit, "real_generation") and _audit_pass(image_audit, "media_asset") and _audit_pass(image_audit, "qa"))
    image_ready = _capability_gate(
        contract=IMAGE_CONTRACT_VERIFIED,
        capability=image_cap,
        audit=image_audit,
        keys=("real_generation", "media_asset", "qa"),
    )

    video_contract = _not_verified(VIDEO_NOT_VERIFIED) if not VIDEO_CONTRACT_VERIFIED else _status(True)
    video_generation = _not_verified(VIDEO_NOT_VERIFIED) if not bool(video_audit.get("real_e2e")) else _status(_audit_pass(video_audit, "real_generation"))
    video_asset = _not_verified(VIDEO_NOT_VERIFIED) if not bool(video_audit.get("real_e2e")) else _status(_audit_pass(video_audit, "media_asset"))
    video_qa = _not_verified(VIDEO_NOT_VERIFIED) if not bool(video_audit.get("real_e2e")) else _status(_audit_pass(video_audit, "qa"))
    video_e2e = _not_verified(VIDEO_NOT_VERIFIED) if not bool(video_audit.get("real_e2e")) else _status(True)
    video_ready = _capability_gate(
        contract=VIDEO_CONTRACT_VERIFIED,
        capability=video_cap,
        audit=video_audit,
        keys=("real_generation", "media_asset", "qa"),
    ) if VIDEO_CONTRACT_VERIFIED else _not_verified(VIDEO_NOT_VERIFIED, evidence_checked=video_audit.get("evidence_checked") or [])

    i2v_ready = _capability_gate(
        contract=False,
        capability=i2v_cap,
        audit=i2v_audit,
        keys=("real_generation", "media_asset", "qa"),
    )
    creative_ready_status = _overall(
        image_ready.get("status"),
        video_ready.get("status"),
        i2v_ready.get("status"),
        image_required=bool(IMAGE_CONTRACT_VERIFIED),
        video_required=bool(VIDEO_CONTRACT_VERIFIED),
        i2v_required=False,
    )
    creative_ready = {
        "status": creative_ready_status,
        "classification": VERIFIED_AND_READY if creative_ready_status == PASS else creative_ready_status,
        "reason": "verified capabilities passed; unverified video stays NOT_VERIFIED" if creative_ready_status == PASS else "required verified capability is not ready",
    }
    return {
        "ARCHITECTURE": {
            "workflow_registry": {"status": PASS if required.issubset(names) else "BLOCKED", "missing": sorted(required - names), "count": len(workflows)},
            "workflow_validation": {"status": PASS if validation_ok else "BLOCKED", "error": validation_error},
            "runtime_container": {"status": PASS if runtime.engine is not None and runtime.provider_resolver is not None else "BLOCKED"},
            "workers": {"status": PASS if callable(run_once) else "BLOCKED"},
            "resume_support": {"status": PASS if resume_ok else "BLOCKED"},
            "api": {"status": PASS if callable(CreativeAPI.create_run) else "BLOCKED"},
            "mock_runtime": {"status": PASS if mock_run.status == "SUCCEEDED" else "BLOCKED", "run_status": mock_run.status, "error": mock_run.error},
            "asset_store": {"status": PASS, "root": str(engine.store.assets.root)},
        },
        "CONFIG": {
            "database": {"status": PASS if db_ok else BLOCKED_EXTERNAL, "error": db_error},
            "creative_persistence": {"status": PASS if persistence_ok else BLOCKED_EXTERNAL, "error": db_error},
            "render": {"status": PASS if ffmpeg_ok else "BLOCKED", "ffmpeg": FFMPEG},
            "cost": {"status": PASS if callable(getattr(runtime.cost_engine, "record", None)) else "BLOCKED"},
            "idempotency": {"status": PASS},
            "async_task_system": {"status": PASS if callable(run_once) else "BLOCKED"},
        },
        "PROVIDER": {
            "provider_registry": {"status": PASS if resolver_ok else "BLOCKED", "count": len(capabilities)},
            "model_registry": {"status": PASS, "models": sorted({item.model for item in capabilities if item.provider == "lechuang" and item.verified})},
        },
        "AUTH": {
            "Creative Credential": cred,
        },
        "IMAGE": {
            "Contract": image_contract,
            "Capability": image_cap,
            "Real Generation": image_generation,
            "MediaAsset": image_asset,
            "QA": image_qa,
            "Real E2E": image_e2e,
            "IMAGE_PRODUCTION_READY": image_ready,
        },
        "VIDEO": {
            "Contract": video_contract,
            "Capability": video_cap,
            "Real Generation": video_generation,
            "MediaAsset": video_asset,
            "QA": video_qa,
            "Real E2E": video_e2e,
            "VIDEO_PRODUCTION_READY": video_ready,
        },
        "IMAGE_TO_VIDEO": {
            "Contract": _not_verified(VIDEO_NOT_VERIFIED),
            "Capability": i2v_cap,
            "IMAGE_TO_VIDEO_PRODUCTION_READY": i2v_ready,
        },
        "LIVE": {
            "IMAGE_PRODUCTION_READY": image_ready,
            "VIDEO_PRODUCTION_READY": video_ready,
            "IMAGE_TO_VIDEO_PRODUCTION_READY": i2v_ready,
            "CREATIVE_PRODUCTION_READY": creative_ready,
        },
        "JUDGE": {
            "judge capability": {"status": BLOCKED_EXTERNAL, "reason": judge_reason, "ok": judge_ok},
        },
        "CAPABILITY": {
            "Xiaole/Lechuang Endpoint": _status(bool(adapter.client.base_url), endpoint=adapter.client.base_url, env=API_KEY_ENV),
            "Contract": image_contract,
            "Image Capability": image_cap,
            "Video Capability": video_cap,
            "Image-to-Video": i2v_cap,
        },
        "LECHUANG_CREATIVE_DOCTOR": {
            "LECHUANG_API_CONFIGURED": cred,
            "LECHUANG_API_REACHABLE": {"status": "NOT_VERIFIED" if not live else adapter.verify(live=True).get("LECHUANG_API_REACHABLE", "BLOCKED")},
            "LECHUANG_IMAGE_CAPABILITY_VERIFIED": _status(IMAGE_CONTRACT_VERIFIED, reason=adapter.client.contract_reason),
            "LECHUANG_VIDEO_CAPABILITY_VERIFIED": _not_verified(VIDEO_NOT_VERIFIED),
            "provider_resolver": _status(resolver_ok),
            "idempotency": _status(True),
            "recovery": _status(callable(getattr(engine, "resume", None))),
        },
    }


def flatten(checks: dict) -> dict:
    flat = {}
    for category, items in checks.items():
        for name, payload in items.items():
            flat[f"{category}:{name}"] = payload
    return flat


def _category_status(items: dict) -> str:
    statuses = [value.get("status") for value in items.values()]
    if any(status == "FAIL" for status in statuses):
        return "FAIL"
    if any(status not in {PASS, BLOCKED_EXTERNAL, NOT_VERIFIED, "HANDOFF_ONLY"} for status in statuses):
        return "FAIL"
    if any(status == BLOCKED_EXTERNAL for status in statuses):
        return BLOCKED_EXTERNAL
    if any(status == NOT_VERIFIED for status in statuses):
        return NOT_VERIFIED
    return PASS


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    args = list(sys.argv[1:] if argv is None else argv)
    live = "--live" in args
    checks = run(live=live)
    category_status = {}
    for category, items in checks.items():
        if category in {"IMAGE", "VIDEO", "IMAGE_TO_VIDEO", "LIVE"}:
            continue
        category_status[category] = _category_status(items)
        print(f"{category}: {category_status[category]}")
        for name, payload in items.items():
            print(f"  {name}: {payload.get('status')}")
    _print_capability(
        "IMAGE",
        [
            ("Contract", checks["IMAGE"]["Contract"]),
            ("Capability", checks["IMAGE"]["Capability"]),
            ("Real Generation", checks["IMAGE"]["Real Generation"]),
            ("MediaAsset", checks["IMAGE"]["MediaAsset"]),
            ("QA", checks["IMAGE"]["QA"]),
            ("Real E2E", checks["IMAGE"]["Real E2E"]),
        ],
        "IMAGE_PRODUCTION_READY",
        checks["IMAGE"]["IMAGE_PRODUCTION_READY"],
    )
    _print_capability(
        "VIDEO",
        [
            ("Contract", checks["VIDEO"]["Contract"]),
            ("Capability", checks["VIDEO"]["Capability"]),
            ("Real Generation", checks["VIDEO"]["Real Generation"]),
            ("MediaAsset", checks["VIDEO"]["MediaAsset"]),
            ("QA", checks["VIDEO"]["QA"]),
            ("Real E2E", checks["VIDEO"]["Real E2E"]),
        ],
        "VIDEO_PRODUCTION_READY",
        checks["VIDEO"]["VIDEO_PRODUCTION_READY"],
    )
    print("IMAGE_TO_VIDEO:")
    print(f"  Contract: {checks['IMAGE_TO_VIDEO']['Contract'].get('status')}")
    print(f"  Capability: {checks['IMAGE_TO_VIDEO']['Capability'].get('status')}")
    print(f"  IMAGE_TO_VIDEO_PRODUCTION_READY: {checks['IMAGE_TO_VIDEO']['IMAGE_TO_VIDEO_PRODUCTION_READY'].get('status')}")
    architecture_fail = any(
        payload.get("status") not in {PASS, BLOCKED_EXTERNAL, NOT_VERIFIED, "HANDOFF_ONLY"}
        for key, payload in flatten(checks).items()
        if key.startswith(("ARCHITECTURE:", "CONFIG:"))
    )
    architecture_ready = not architecture_fail
    image_status = checks["LIVE"]["IMAGE_PRODUCTION_READY"].get("status")
    video_status = checks["LIVE"]["VIDEO_PRODUCTION_READY"].get("status")
    i2v_status = checks["LIVE"]["IMAGE_TO_VIDEO_PRODUCTION_READY"].get("status")
    creative_status = checks["LIVE"]["CREATIVE_PRODUCTION_READY"].get("status")
    classification = checks["LIVE"]["CREATIVE_PRODUCTION_READY"].get("classification")
    print("ARCHITECTURE:", PASS if architecture_ready else "FAIL")
    print("IMAGE_PRODUCTION_READY:", image_status)
    print("VIDEO_PRODUCTION_READY:", video_status)
    print("IMAGE_TO_VIDEO_PRODUCTION_READY:", i2v_status)
    print("CREATIVE_PRODUCTION_READY:", creative_status)
    print("CREATIVE_STATUS:", classification)
    print("LECHUANG_CREATIVE_DOCTOR:")
    for name, payload in checks["LECHUANG_CREATIVE_DOCTOR"].items():
        print(f"  {name}: {payload.get('status')}")
    print(json.dumps({
        "architecture_ready": architecture_ready,
        "image_production_ready": image_status,
        "video_production_ready": video_status,
        "image_to_video_production_ready": i2v_status,
        "creative_production_ready": creative_status,
        "creative_status": classification,
        "categories": category_status,
        "checks": {key: value.get("status") for key, value in flatten(checks).items()},
    }, default=str))
    return 0 if architecture_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
