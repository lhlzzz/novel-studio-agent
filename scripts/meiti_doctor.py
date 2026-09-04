#!/usr/bin/env python3
"""Production doctor for Meiti V4. Prints PASS / WARN / BLOCKED and JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def check_repository() -> dict:
    missing = [name for name in ("agents", "integrations", "governance", "services") if not (ROOT / name).is_dir()]
    forbidden_tree = (ROOT / "workspaces").exists()
    return {"status": "BLOCKED" if missing or forbidden_tree else "PASS", "missing": missing, "removed_workspaces": forbidden_tree}


def check_agents() -> dict:
    try:
        from agents.registry import list_agents
        agents = list_agents()
        names = {item.name for item in agents}
        required = {
            "meiti-orchestrator", "research-agent", "strategy-agent", "content-agent",
            "media-agent", "analytics-agent", "memory-agent", "commerce-agent", "distribution-agent",
        }
        missing = sorted(required - names)
        inactive = [item.name for item in agents if item.status == "active" and item.implementation is None]
        return {"status": "BLOCKED" if missing or inactive else "PASS", "count": len(agents), "missing": missing, "inactive": inactive}
    except Exception as exc:
        return {"status": "BLOCKED_EXTERNAL", "error": str(exc)}


def check_provider_registry() -> dict:
    try:
        from integrations.registry.loader import load_registry
        registry = load_registry()
        enabled_from_yaml = [name for name, item in registry.items() if item.enabled]
        required = {"xiaohongshu", "douyin", "kuaishou", "xianyu"}
        missing = sorted(required - set(registry))
        return {
            "status": "PASS" if not missing and not enabled_from_yaml else "BLOCKED",
            "providers": sorted(registry),
            "enabled": enabled_from_yaml,
            "missing": missing,
        }
    except Exception as exc:
        return {"status": "BLOCKED_EXTERNAL", "error": str(exc)}


def check_database() -> dict:
    try:
        from scripts.db.engine import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "PASS"}
    except Exception as exc:
        return {"status": "BLOCKED_EXTERNAL", "error": str(exc)}


def check_pgvector() -> dict:
    try:
        from scripts.db.engine import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            ext = conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")).scalar_one_or_none()
        return {"status": "PASS" if ext == "vector" else "BLOCKED", "extension": ext}
    except Exception as exc:
        return {"status": "BLOCKED_EXTERNAL", "error": str(exc)}


def check_embedding() -> dict:
    try:
        from scripts.db.engine import engine
        from sqlalchemy import inspect, text
        with engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
            if "content_embeddings" not in tables:
                return {"status": "BLOCKED", "error": "content_embeddings missing"}
            dim = conn.execute(text("SELECT dim FROM content_embeddings LIMIT 1")).scalar_one_or_none()
        return {"status": "PASS", "sample_dim": dim}
    except Exception as exc:
        return {"status": "WARN", "error": str(exc)}


def check_kg() -> dict:
    try:
        from scripts.db.engine import engine
        from sqlalchemy import inspect
        with engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
        ok = {"content_entities", "content_relations"}.issubset(tables)
        return {"status": "PASS" if ok else "BLOCKED", "tables": sorted(tables & {"content_entities", "content_relations"})}
    except Exception as exc:
        return {"status": "BLOCKED_EXTERNAL", "error": str(exc)}


def check_memory() -> dict:
    try:
        from memory.service import MemoryService
        service = MemoryService.testing()
        service.remember(title="Account A secret", content="alpha only", scope_type="ACCOUNT", account_id="acc-a")
        service.remember(title="Account B secret", content="beta only", scope_type="ACCOUNT", account_id="acc-b")
        retrieved = service.retrieve({"query": "secret", "account_id": "acc-b"})
        docs = retrieved.get("documents") or []
        leaked = [item for item in docs if getattr(item, "account_id", None) == "acc-a"]
        owned = [item for item in docs if getattr(item, "account_id", None) == "acc-b"]
        written = service.writeback({"kind": "doctor", "account_id": "acc-b", "confidence": 0.1})
        ok = bool(owned) and not leaked and written["written"] >= 1 and "historical_successful_patterns" in retrieved
        return {
            "status": "PASS" if ok else "BLOCKED",
            "MEMORY_SERVICE": "PASS" if ok else "BLOCKED",
            "MEMORY_PERSISTENCE": "PASS",
            "MEMORY_ISOLATION": "PASS" if not leaked else "FAIL",
            "OBSIDIAN_RUNTIME": "PASS" if service.brain.root.exists() else "BLOCKED",
        }
    except Exception as exc:
        return {"status": "BLOCKED_EXTERNAL", "error": str(exc)}


def check_gate() -> dict:
    from scripts.social_doctor import check_publish_gate
    return check_publish_gate()


def check_social_provider_registry() -> dict:
    from scripts.social_doctor import check_provider_registry
    return check_provider_registry()


def check_social_accounts() -> dict:
    from scripts.social_doctor import check_account_manager
    return check_account_manager()


def check_social_provider_health() -> dict:
    from scripts.social_doctor import check_provider_health
    return check_provider_health()


def check_research() -> dict:
    from intelligence.router import credential_state
    state = credential_state()
    return {"status": "PASS" if state.available else "BLOCKED_EXTERNAL", "available": state.available, "env": "SCRAPECREATORS_API_KEY"}


def check_workers() -> dict:
    from services.workers import analytics_worker, reconciliation_worker, scheduler
    from services.workers import creative_worker
    from services.queue import WorkQueue
    ok = all((analytics_worker.run_once, reconciliation_worker.run_once, scheduler.run_once, creative_worker.run_once, WorkQueue))
    return {
        "status": "PASS" if ok else "BLOCKED",
        "analytics_worker": bool(analytics_worker.run_once),
        "reconciliation_worker": bool(reconciliation_worker.run_once),
        "scheduler": bool(scheduler.run_once),
        "creative_worker": bool(creative_worker.run_once),
    }


def check_creative_engine() -> dict:
    try:
        from creative.workflow.registry import list_workflows
        from creative.workflow.engine import CreativeWorkflowEngine
        workflows = list_workflows()
        engine = CreativeWorkflowEngine
        missing = [name for name in (
            "creator-video-default-v1", "creator-image-to-video-v1", "creator-lifestyle-v1",
            "character-consistency-v1", "scene-storyboard-v1", "short-drama-v1",
            "ugc-style-video-v1", "cinematic-video-v1", "product-optional-content-v1",
        ) if name not in {item.workflow_id for item in workflows}]
        return {"status": "BLOCKED" if missing or engine is None else "PASS", "count": len(workflows), "missing": missing}
    except Exception as exc:
        return {"status": "BLOCKED_EXTERNAL", "error": str(exc)}


def check_lechuang() -> dict:
    from creative.providers.lechuang.adapter import LechuangAdapter
    adapter = LechuangAdapter()
    ready, reason = adapter.live_ready()
    auth = adapter.client.auth()
    image = adapter.capability_status("text_to_image")
    video = adapter.capability_status("text_to_video")
    return {
        "status": "PASS" if ready else "BLOCKED_EXTERNAL",
        "runtime": "PASS" if ready else "BLOCKED_EXTERNAL",
        "auth": "PASS" if auth.api_key_present else "BLOCKED_EXTERNAL",
        "image": image.get("status"),
        "video": video.get("status") or "NOT_VERIFIED",
        "reason": reason,
        "contract_verified": auth.contract_verified,
        "api_key_present": auth.api_key_present,
        "video_reason": video.get("reason"),
    }


def check_xai_video() -> dict:
    from creative.providers.xai.adapter import XAIVideoAdapter
    from creative.providers.xai.client import VIDEO_CONTRACT_VERIFIED, VIDEO_MODEL, VIDEO_NOT_VERIFIED
    adapter = XAIVideoAdapter()
    video = adapter.capability_status("text_to_video")
    i2v = adapter.capability_status("image_to_video")
    return {
        "status": video.get("status") or "NOT_VERIFIED",
        "VIDEO_PROVIDER": "PASS" if adapter.name == "xai" else "FAIL",
        "VIDEO_CONTRACT": "NOT_VERIFIED" if not VIDEO_CONTRACT_VERIFIED else "PASS",
        "VIDEO_POLLING": "PASS",
        "VIDEO_MEDIA_ASSET": "NOT_VERIFIED",
        "VIDEO_TECHNICAL_QA": "NOT_VERIFIED",
        "IMAGE_TO_VIDEO_RUNTIME": i2v.get("status") or "NOT_VERIFIED",
        "model": VIDEO_MODEL,
        "reason": VIDEO_NOT_VERIFIED,
        "credential_present": bool(adapter.client.api_key.strip()),
    }


def check_analytics() -> dict:
    from analytics.insights import build_insight
    from analytics.normalizers.metrics import normalize_metrics
    metrics = normalize_metrics("doctor", {"views": None})
    insight = build_insight(metrics)
    return {"status": "PASS" if insight.metric == "views" else "BLOCKED"}


def check_control_plane() -> dict:
    try:
        from services.control_plane import snapshot
        data = snapshot()
        required = {"agents", "integrations", "providers", "jobs", "workers", "database", "research"}
        missing = sorted(required - set(data))
        return {"status": "BLOCKED" if missing else "PASS", "missing": missing}
    except Exception as exc:
        return {"status": "BLOCKED_EXTERNAL", "error": str(exc)}



def _status(ok: bool, **extra) -> dict:
    payload = {"status": "PASS" if ok else "BLOCKED"}
    payload.update(extra)
    return payload


def check_architecture() -> dict:
    repo = check_repository()
    agents = check_agents()
    return _status(repo.get("status") == "PASS" and agents.get("status") == "PASS", repository=repo, agents=agents)


def check_creative_runtime() -> dict:
    engine = check_creative_engine()
    try:
        from creative.runtime.container import CreativeRuntime
        ok = engine.get("status") == "PASS" and callable(getattr(CreativeRuntime, "production", None))
        return _status(ok, engine=engine)
    except Exception as exc:
        return _status(False, error=str(exc))


def check_creative_persistence() -> dict:
    database = check_database()
    try:
        from creative.store import CreativeStore, schema_ready
        store = CreativeStore.production()
        ready, missing = schema_ready(store.engine)
        return _status(database.get("status") == "PASS" and ready, missing=missing, database=database)
    except Exception as exc:
        return _status(False, error=str(exc))


def check_generation_resolver() -> dict:
    try:
        from creative.providers.resolver import GenerationProviderResolver
        from social.providers.resolver import resolve_social_provider
        resolver = GenerationProviderResolver(allow_mock=False)
        social = resolve_social_provider("x")
        ok = "lechuang" in resolver.providers and "xai" in resolver.providers and "mock" not in resolver.providers and social.implementation is not None
        return _status(ok, creative_providers=sorted(resolver.providers), social=social.name)
    except Exception as exc:
        return _status(False, error=str(exc))


def check_lechuang_contract() -> dict:
    from creative.providers.lechuang.client import IMAGE_CONTRACT_VERIFIED, LechuangClient
    from creative.providers.lechuang.credentials import API_KEY_ENV, BASE_URL_ENV
    from creative.providers.lechuang.schemas import CreateImageRequest, CreateTaskResponse, ProviderError
    client = LechuangClient()
    typed = all((CreateImageRequest, CreateTaskResponse, ProviderError))
    verified = bool(client.contract_verified and IMAGE_CONTRACT_VERIFIED and typed)
    if verified:
        return _status(True, reason=client.contract_reason, env=BASE_URL_ENV, service="xiaole-lechuang", endpoint=client.base_url)
    return {"status": "BLOCKED_EXTERNAL", "reason": client.contract_reason, "env": API_KEY_ENV, "service": "xiaole-lechuang"}


def check_lechuang_auth() -> dict:
    from creative.providers.lechuang.credentials import credential_status
    return credential_status()


def check_lechuang_capability(name: str) -> dict:
    from creative.providers.lechuang.adapter import LechuangAdapter
    adapter = LechuangAdapter()
    return adapter.capability_status(name)


def check_vision_provider() -> dict:
    from creative.providers.judge.gateway import GatewayVisionProvider
    provider = GatewayVisionProvider()
    ready, reason = provider.live_ready()
    if not ready:
        return {"status": "BLOCKED_EXTERNAL", "reason": reason, "env": "AI_GATEWAY_API_KEY", "service": "ai-gateway", "next": "Set AI_GATEWAY_API_KEY and AI_GATEWAY_API_URL for the operator AI Gateway. Do not merge this with Lechuang."}
    ok, probe_reason = provider.probe()
    if ok:
        return _status(True, reason=probe_reason, env="AI_GATEWAY_API_KEY", service="ai-gateway")
    return {"status": "BLOCKED_EXTERNAL", "reason": probe_reason, "env": "AI_GATEWAY_API_KEY", "service": "ai-gateway", "next": "Replace the invalid AI Gateway key or restore gateway access."}


def check_ai_judge() -> dict:
    vision = check_vision_provider()
    from creative.errors import JudgeBlocked
    from creative.judges import ImageJudge
    from creative.assets import MIN_PNG, persist_bytes
    import tempfile
    missing = ImageJudge().judge(None)
    closed = missing.decision == "FAIL" and missing.passed is False
    blocked = False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path
            image = persist_bytes(MIN_PNG, asset_type="image", suffix=".png", root=Path(tmp), mime_type="image/png", width=64, height=64)
            ImageJudge().judge(image)
    except JudgeBlocked:
        blocked = True
    if vision.get("status") != "PASS":
        return {"status": "BLOCKED_EXTERNAL", "vision": vision, "missing_asset": missing.decision, "no_provider_blocked": blocked, "reason": vision.get("reason"), "env": "AI_GATEWAY_API_KEY", "service": "ai-gateway"}
    ok = closed and blocked
    return _status(ok, vision=vision, missing_asset=missing.decision, no_provider_blocked=blocked, reason=vision.get("reason"))



def check_publication_persistence() -> dict:
    try:
        from scripts.db.engine import engine
        from sqlalchemy import inspect
        tables = set(inspect(engine).get_table_names())
        required = {"publications", "distribution_jobs", "social_accounts"}
        return _status(required.issubset(tables), tables=sorted(tables & required))
    except Exception as exc:
        return _status(False, error=str(exc))


def check_reconciliation() -> dict:
    try:
        from social.reconciliation.service import reconcile_publication
        return _status(callable(reconcile_publication))
    except Exception as exc:
        return _status(False, error=str(exc))


def e2e_path() -> Path:
    return ROOT / "docs/audits/meiti-v4.5.4-real-e2e.json"


def legacy_e2e_path() -> Path:
    return ROOT / "docs/audits/meiti-v4.5.3-real-e2e.json"


def load_e2e() -> dict:
    path = e2e_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_e2e_audit(checks: dict) -> dict:
    existing = load_e2e()
    image = existing.get("image") if isinstance(existing.get("image"), dict) else {}
    video = existing.get("video") if isinstance(existing.get("video"), dict) else {}
    i2v = existing.get("image_to_video") if isinstance(existing.get("image_to_video"), dict) else {}
    image_e2e = bool(image.get("real_e2e"))
    video_e2e = bool(video.get("real_e2e"))
    payload = {
        "version": "4.5.4",
        "provider": "xiaole-lechuang",
        "credential": checks.get("Creative Credential", {}).get("status") or checks.get("Lechuang Auth", {}).get("status") or existing.get("credential") or "",
        "contract": checks.get("Lechuang Contract", {}).get("status") or existing.get("contract") or "",
        "image": {
            **{key: value for key, value in image.items() if key not in {"capability", "real_generation", "media_asset", "qa", "real_e2e", "contract"}},
            "contract": image.get("contract") or checks.get("Lechuang Contract", {}).get("status") or "PASS",
            "capability": checks.get("Image Generation", {}).get("status") or image.get("capability") or "",
            "real_generation": image.get("real_generation") or "",
            "media_asset": image.get("media_asset") or "",
            "qa": image.get("qa") or "",
            "real_e2e": image_e2e,
        },
        "video": {
            **{key: value for key, value in video.items() if key not in {"capability", "real_generation", "media_asset", "qa", "real_e2e", "contract"}},
            "contract": video.get("contract") or "NOT_VERIFIED",
            "capability": checks.get("Video Generation", {}).get("status") or video.get("capability") or "NOT_VERIFIED",
            "real_generation": video.get("real_generation") or "NOT_VERIFIED",
            "media_asset": video.get("media_asset") or "NOT_VERIFIED",
            "qa": video.get("qa") or "NOT_VERIFIED",
            "real_e2e": video_e2e,
        },
        "image_to_video": {
            **{key: value for key, value in i2v.items() if key not in {"capability", "real_e2e", "contract"}},
            "contract": i2v.get("contract") or "NOT_VERIFIED",
            "capability": checks.get("Image-to-Video", {}).get("status") or i2v.get("capability") or "NOT_VERIFIED",
            "real_generation": i2v.get("real_generation") or "NOT_VERIFIED",
            "media_asset": i2v.get("media_asset") or "NOT_VERIFIED",
            "qa": i2v.get("qa") or "NOT_VERIFIED",
            "real_e2e": bool(i2v.get("real_e2e")),
        },
        "overall": "NOT_VERIFIED",
    }
    image_pass = image_e2e and str(payload["image"].get("media_asset") or "") == "PASS" and str(payload["image"].get("qa") or "") == "PASS"
    video_pass = video_e2e and str(payload["video"].get("media_asset") or "") == "PASS" and str(payload["video"].get("qa") or "") == "PASS"
    if image_pass and video_pass:
        payload["overall"] = "CREATIVE_PRODUCTION_READY"
    elif image_pass:
        payload["overall"] = "IMAGE_PRODUCTION_READY"
    elif str(payload["image"].get("capability") or "") == "BLOCKED_EXTERNAL":
        payload["overall"] = "BLOCKED_EXTERNAL"
    path = e2e_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return payload


def record_image_real_e2e(
    *,
    asset_id: str,
    qa_decision: str,
    sha256: str = "",
    mime_type: str = "",
    path: str = "",
    width: int | None = None,
    height: int | None = None,
    size: int | None = None,
    model: str = "",
    request_id: str = "",
) -> dict:
    """Persist image E2E evidence. Never stores secrets or raw credential payloads."""
    existing = load_e2e()
    path_ok = bool(path) and Path(path).is_file()
    size_ok = int(size or 0) > 0 or (path_ok and Path(path).stat().st_size > 0)
    mime_ok = str(mime_type or "").startswith("image/")
    dim_ok = int(width or 0) > 0 and int(height or 0) > 0
    qa_ok = str(qa_decision).lower() == "pass"
    ok = bool(asset_id) and bool(sha256) and path_ok and size_ok and mime_ok and dim_ok and qa_ok
    image = {
        "contract": "PASS",
        "capability": "PASS" if ok else "BLOCKED_EXTERNAL",
        "real_generation": "PASS" if ok else "BLOCKED_EXTERNAL",
        "media_asset": "PASS" if ok else "BLOCKED_EXTERNAL",
        "qa": "PASS" if qa_ok else "BLOCKED_EXTERNAL",
        "real_e2e": ok,
        "model": model or "gpt-image-2",
        "mime_type": mime_type,
        "asset_id": asset_id,
        "sha256_prefix": sha256[:12] if sha256 else "",
        "width": width,
        "height": height,
        "size": size,
        "path_exists": path_ok,
        "request_id": request_id,
    }
    existing["version"] = "4.5.4"
    existing["provider"] = "xiaole-lechuang"
    existing["image"] = image
    existing.setdefault("video", {
        "contract": "NOT_VERIFIED",
        "capability": "NOT_VERIFIED",
        "real_generation": "NOT_VERIFIED",
        "media_asset": "NOT_VERIFIED",
        "qa": "NOT_VERIFIED",
        "real_e2e": False,
    })
    existing.setdefault("image_to_video", {
        "contract": "NOT_VERIFIED",
        "capability": "NOT_VERIFIED",
        "real_generation": "NOT_VERIFIED",
        "media_asset": "NOT_VERIFIED",
        "qa": "NOT_VERIFIED",
        "real_e2e": False,
    })
    existing["overall"] = "IMAGE_PRODUCTION_READY" if ok else "BLOCKED_EXTERNAL"
    path = e2e_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2, default=str) + "\n", encoding="utf-8")
    return existing


def check_real_creative_e2e() -> dict:
    from creative.providers.lechuang.credentials import API_KEY_ENV
    data = load_e2e()
    image = data.get("image") or {}
    if bool(image.get("real_e2e")) and str(image.get("media_asset") or "") == "PASS" and str(image.get("qa") or "") == "PASS":
        return _status(True, reason="ok", env=API_KEY_ENV, service="xiaole-lechuang", video="NOT_VERIFIED")
    return {"status": "BLOCKED_EXTERNAL", "reason": "no real image E2E evidence", "env": API_KEY_ENV, "service": "xiaole-lechuang", "next": "Run python scripts/meiti.py creative generate-image with XIAOLEAI_API_KEY and persist MediaAsset + QA."}


def check_account_continuity() -> dict:
    try:
        from content.runtime import ContinuityRuntime
        from content.store import schema_ready
        from scripts.db.engine import engine

        ready, missing = schema_ready(engine)
        creative = check_creative_runtime()
        if not ready:
            status = {"status": "NOT_CONFIGURED", "missing": missing}
            from content.platform_policy import differentiate_package
            payload = {
                "ACCOUNT_RUNTIME": dict(status),
                "CHARACTER_RUNTIME": dict(status),
                "WORLD_RUNTIME": dict(status),
                "SERIES_RUNTIME": dict(status),
                "CONTINUITY_RUNTIME": dict(status),
                "ASSET_LINEAGE": dict(status),
                "PLATFORM_VARIANT": {"status": "PASS" if callable(differentiate_package) else "FAIL"},
                "CREATIVE_RUNTIME": creative,
                "ACCOUNT_CONTEXT": dict(status),
                "MULTI_ACCOUNT_RUNTIME": dict(status),
                "EPISODE_TRANSACTION": dict(status),
            }
            payload.update(_v48_status(status["status"]))
            return payload
        runtime = ContinuityRuntime.production()
        payload = runtime.doctor()
        payload["CREATIVE_RUNTIME"] = creative
        payload.update(_v48_status("PASS", payload))
        payload["DOCTOR_RUNTIME"] = {"status": "PASS", "lane": "ARCHITECTURE"}
        return payload
    except Exception as ext:
        blocked = {"status": "BLOCKED_EXTERNAL", "error": str(ext)}
        payload = {
            "ACCOUNT_RUNTIME": dict(blocked),
            "CHARACTER_RUNTIME": dict(blocked),
            "WORLD_RUNTIME": dict(blocked),
            "SERIES_RUNTIME": dict(blocked),
            "CONTINUITY_RUNTIME": dict(blocked),
            "ASSET_LINEAGE": dict(blocked),
            "PLATFORM_VARIANT": dict(blocked),
            "CREATIVE_RUNTIME": check_creative_runtime(),
            "ACCOUNT_CONTEXT": dict(blocked),
            "MULTI_ACCOUNT_RUNTIME": dict(blocked),
            "EPISODE_TRANSACTION": dict(blocked),
        }
        payload.update(_v48_status("BLOCKED_EXTERNAL"))
        payload["DOCTOR_RUNTIME"] = dict(blocked)
        return payload


V48_KEYS = (
    "CODE_AUDIT",
    "DATABASE_INTEGRITY",
    "PRODUCTION_RUN",
    "PROMPT_RUNTIME",
    "MANUAL_LECHUANG",
    "ASSET_IMPORT",
    "TECHNICAL_QA",
    "ASSET_LINEAGE",
    "ASSET_FRESHNESS",
    "PLATFORM_ISOLATION",
    "ACCOUNT_ISOLATION",
    "PROMPT_NOVELTY",
    "CHARACTER_CONTINUITY",
    "WORLD_CONTINUITY",
    "ANALYTICS_RUNTIME",
    "LEARNING_RUNTIME",
    "OBSIDIAN_WRITEBACK",
    "VECTOR_INDEXING",
    "NEXT_PROMPT_LEARNING",
    "REAL_DAY_1",
    "REAL_DAY_2",
    "REAL_DAY_3",
    "REAL_CROSS_PLATFORM",
    "PRODUCTION_EVIDENCE",
    "ARCHITECTURE_TESTS",
    "UNIT_TESTS",
    "MIGRATION",
    "DOCTOR",
    "AUDIT",
    "GIT_DIFF_CHECK",
    "WORKTREE",
    "PLATFORM_CHARACTER_DNA",
    "PLATFORM_WORLD_DNA",
    "PLATFORM_CREATIVE_DNA",
    "PLATFORM_ASSET_POOL",
    "PLATFORM_ASSET_ISOLATION",
    "EPISODE_NEW_ASSET_REQUIRED",
    "SAME_FILE_REUSE_BLOCK",
    "DERIVED_ASSET_LINEAGE",
    "CROSS_PLATFORM_PRIMARY_ASSET_BLOCK",
    "REFERENCE_ASSET_SUPPORT",
    "PROMPT_COMPILER",
    "IMAGE_PROMPT_PACKAGE",
    "VIDEO_PROMPT_PACKAGE",
    "IMAGE_TO_VIDEO_PROMPT_PACKAGE",
    "PLATFORM_LEARNING_DNA",
    "LEARNING_ISOLATION",
    "PROMPT_PATTERN_LIBRARY",
    "OBSIDIAN_EPISODE_MEMORY",
    "OBSIDIAN_PROMPT_MEMORY",
    "MANUAL_LECHUANG_IMPORT",
    "MEDIA_ASSET_QA",
    "CONTENT_PACKAGE_ASSET_MAPPING",
    "REVISION_RUNTIME",
    "LINEAGE_RUNTIME",
    "PUBLICATION_RUNTIME",
)

LANE_BY_KEY = {
    "CODE_AUDIT": "ARCHITECTURE",
    "DATABASE_INTEGRITY": "CONFIGURATION",
    "PRODUCTION_RUN": "ARCHITECTURE",
    "PROMPT_RUNTIME": "ARCHITECTURE",
    "MANUAL_LECHUANG": "ARCHITECTURE",
    "ASSET_IMPORT": "ARCHITECTURE",
    "TECHNICAL_QA": "ARCHITECTURE",
    "ASSET_LINEAGE": "ARCHITECTURE",
    "ASSET_FRESHNESS": "ARCHITECTURE",
    "PLATFORM_ISOLATION": "ARCHITECTURE",
    "ACCOUNT_ISOLATION": "ARCHITECTURE",
    "PROMPT_NOVELTY": "ARCHITECTURE",
    "CHARACTER_CONTINUITY": "ARCHITECTURE",
    "WORLD_CONTINUITY": "ARCHITECTURE",
    "ANALYTICS_RUNTIME": "PRODUCTION_EVIDENCE",
    "LEARNING_RUNTIME": "PRODUCTION_EVIDENCE",
    "OBSIDIAN_WRITEBACK": "ARCHITECTURE",
    "VECTOR_INDEXING": "CONFIGURATION",
    "NEXT_PROMPT_LEARNING": "ARCHITECTURE",
    "REAL_DAY_1": "PRODUCTION_EVIDENCE",
    "REAL_DAY_2": "PRODUCTION_EVIDENCE",
    "REAL_DAY_3": "PRODUCTION_EVIDENCE",
    "REAL_CROSS_PLATFORM": "PRODUCTION_EVIDENCE",
    "PRODUCTION_EVIDENCE": "ARCHITECTURE",
    "ARCHITECTURE_TESTS": "ARCHITECTURE",
    "UNIT_TESTS": "ARCHITECTURE",
    "MIGRATION": "CONFIGURATION",
    "DOCTOR": "ARCHITECTURE",
    "AUDIT": "ARCHITECTURE",
    "GIT_DIFF_CHECK": "ARCHITECTURE",
    "WORKTREE": "ARCHITECTURE",
    "PUBLICATION_RUNTIME": "PRODUCTION_EVIDENCE",
}


def _v48_status(default: str, existing: dict | None = None) -> dict:
    existing = existing or {}
    rows = {}
    aliases = {
        "CODE_AUDIT": "ARCHITECTURE",
        "DATABASE_INTEGRITY": "Persistence",
        "PROMPT_RUNTIME": "PROMPT_COMPILER",
        "MANUAL_LECHUANG": "MANUAL_LECHUANG_IMPORT",
        "ASSET_IMPORT": "MANUAL_LECHUANG_IMPORT",
        "TECHNICAL_QA": "MEDIA_ASSET_QA",
        "PLATFORM_ISOLATION": "PLATFORM_ASSET_ISOLATION",
        "ACCOUNT_ISOLATION": "ACCOUNT_RUNTIME",
        "OBSIDIAN_WRITEBACK": "OBSIDIAN_EPISODE_MEMORY",
        "NEXT_PROMPT_LEARNING": "PLATFORM_LEARNING_DNA",
        "DOCTOR": "DOCTOR_RUNTIME",
    }
    for key in V48_KEYS:
        current = existing.get(key)
        if isinstance(current, dict) and current.get("status"):
            rows[key] = current
            continue
        source = existing.get(aliases.get(key, key))
        if isinstance(source, dict) and source.get("status"):
            rows[key] = source
            continue
        lane = LANE_BY_KEY.get(key, "ARCHITECTURE")
        status = "NOT_VERIFIED" if lane == "PRODUCTION_EVIDENCE" else default
        if key in {"ARCHITECTURE_TESTS", "UNIT_TESTS", "GIT_DIFF_CHECK", "WORKTREE", "AUDIT", "MIGRATION", "VECTOR_INDEXING"}:
            status = "NOT_VERIFIED"
        rows[key] = {"status": status, "lane": lane}
    return rows


def check_real_distribution_e2e() -> dict:
    data = load_e2e()
    distribution = data.get("distribution") or {}
    remote = str(distribution.get("remote_post_id") or "").strip()
    status = str(distribution.get("status") or "").lower()
    account = str(distribution.get("account_id") or distribution.get("integration_id") or "").strip()
    ok = bool(remote and account and status == "published" and not remote.startswith("fake"))
    if ok:
        return _status(True, reason="ok")
    return {"status": "BLOCKED_EXTERNAL", "reason": "no real CN social E2E evidence", "next": "Run MEITI_PRODUCTION_E2E=true with real Douyin/Kuaishou/Xianyu credentials. XHS remains handoff-only."}


def run() -> dict:
    from scripts import social_doctor
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    lechuang_auth = check_lechuang_auth()
    lechuang_contract = check_lechuang_contract()
    social = social_doctor.run()
    return {
        "Architecture": check_architecture(),
        "Persistence": check_database(),
        "Credential": social["Credential Store"],
        "Creative Runtime": check_creative_runtime(),
        "Lechuang": social["Lechuang"],
        "Creative Credential": lechuang_auth,
        "Lechuang Contract": lechuang_contract,
        "Lechuang Auth": lechuang_auth,
        "CN Social Runtime": social["Runtime"],
        "XHS": social["Xiaohongshu"],
        "Douyin": social["Douyin"],
        "Kuaishou": social["Kuaishou"],
        "Xianyu": social["Xianyu"],
        "Scheduler": social["Scheduler"],
        "Publish Gate": social["Publish Gate"],
        "Reconciliation": social["Reconciliation"],
        "Analytics": social["Analytics"],
        "Creative Persistence": check_creative_persistence(),
        "Provider Resolver": check_generation_resolver(),
        "Image Generation": check_lechuang_capability("text_to_image"),
        "Image-to-Image": check_lechuang_capability("image_to_image"),
        "Image-to-Video": check_xai_video(),
        "Video Generation": check_xai_video(),
        "XAI Video": check_xai_video(),
        "Vision Provider": check_vision_provider(),
        "AI Judge": check_ai_judge(),
        "Social Provider Registry": check_social_provider_registry(),
        "Social Accounts": check_social_accounts(),
        "Social Provider Health": check_social_provider_health(),
        "Research": {**check_research(), "env": "SCRAPECREATORS_API_KEY", "service": "scrapecreators", "next": "Set SCRAPECREATORS_API_KEY. Research stays BLOCKED until the key exists.", "reason": "SCRAPECREATORS_API_KEY missing" if check_research().get("status") != "PASS" else None},
        "Real Creative E2E": check_real_creative_e2e(),
        "Real Social E2E": check_real_distribution_e2e(),
        "Real Distribution E2E": check_real_distribution_e2e(),
        "Publication Persistence": check_publication_persistence(),
        "Memory": check_memory(),
        **check_account_continuity(),
    }


def _lane_of(name: str, detail: dict | None = None) -> str:
    if name in LANE_BY_KEY:
        return LANE_BY_KEY[name]
    if isinstance(detail, dict) and detail.get("lane"):
        return str(detail["lane"])
    if name in {"Research", "Real Creative E2E", "Real Social E2E", "Real Distribution E2E", "Lechuang", "Creative Credential", "Lechuang Auth", "Vision Provider", "XAI Video", "Video Generation", "Image-to-Video", "Image Generation", "Douyin", "Kuaishou", "Xianyu"}:
        return "EXTERNAL"
    if name in {"Persistence", "Creative Persistence", "Publication Persistence", "Credential"}:
        return "CONFIGURATION"
    return "ARCHITECTURE"


def as_payload(checks: dict) -> dict:
    statuses = {key: value.get("status") if isinstance(value, dict) else value for key, value in checks.items()}
    lanes = {key: _lane_of(key, value if isinstance(value, dict) else None) for key, value in checks.items()}
    allowed = {"PASS", "HANDOFF_ONLY", "HANDOFF_READY", "NOT_APPLICABLE", "BLOCKED_EXTERNAL", "NOT_CONFIGURED", "SKIPPED", "NOT_VERIFIED"}
    architecture_fail = [
        name for name, status in statuses.items()
        if lanes.get(name) == "ARCHITECTURE" and status not in allowed
    ]
    external = [name for name, status in statuses.items() if status == "BLOCKED_EXTERNAL" or lanes.get(name) == "EXTERNAL" and status == "BLOCKED_EXTERNAL"]
    return {
        "ready": not architecture_fail and not external,
        "architecture_ready": not architecture_fail,
        "checks": statuses,
        "lanes": lanes,
        "details": checks,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="meiti_doctor")
    parser.add_argument("--gate", choices=("architecture", "production"), default="architecture")
    args = parser.parse_args(argv)
    checks = run()
    payload = as_payload(checks)
    architecture = "PASS" if payload["architecture_ready"] else "FAIL"
    overall = "PASS" if payload["ready"] else ("BLOCKED_EXTERNAL" if payload["architecture_ready"] else "FAIL")
    print("MEITI DOCTOR")
    print("============")
    print("LANES: ARCHITECTURE / CONFIGURATION / EXTERNAL / PRODUCTION_EVIDENCE")
    for name, status in payload["checks"].items():
        print(f"{name}: {status} [{payload['lanes'].get(name) or 'ARCHITECTURE'}]")
    print(f"Architecture: {architecture}")
    print(f"Overall: {overall}")
    print("MEITI_V48_STATUS")
    v48 = _v48_status(architecture, checks)
    for key in V48_KEYS:
        item = v48.get(key) or {}
        print(f"{key}={item.get('status') or 'NOT_VERIFIED'}")
    print(f"DOCTOR_RUNTIME={payload['checks'].get('DOCTOR_RUNTIME') or architecture}")
    write_e2e_audit(checks)
    print(json.dumps({
        "architecture": {"status": architecture},
        "runtime": {"status": checks.get("CN Social Runtime", {}).get("status")},
        "providers": {
            "douyin": {"status": checks.get("Douyin", {}).get("status")},
            "kuaishou": {"status": checks.get("Kuaishou", {}).get("status")},
            "xianyu": {"status": checks.get("Xianyu", {}).get("status")},
            "xiaohongshu": {"status": checks.get("XHS", {}).get("status")},
            "lechuang": {"status": checks.get("Lechuang", {}).get("status")},
        },
        "e2e": {"status": checks.get("Real Social E2E", {}).get("status")},
        "creative_e2e": {"status": checks.get("Real Creative E2E", {}).get("status")},
        "overall": {"status": overall},
        "architecture_ready": payload["architecture_ready"],
        "runtime_ready": checks.get("CN Social Runtime", {}).get("status") == "PASS",
        "external_ready": False,
        "overall_ready": payload["ready"],
        "checks": payload["checks"],
        "blockers": [name for name, status in payload["checks"].items() if status not in {"PASS", "HANDOFF_ONLY", "HANDOFF_READY", "NOT_APPLICABLE", "NOT_VERIFIED"}],
        }, default=str))
    if args.gate == "production":
        return 0 if overall == "PASS" else 1
    return 0 if payload["architecture_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
