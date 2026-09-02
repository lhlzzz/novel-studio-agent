#!/usr/bin/env python3
"""Production doctor for Meiti V4. Prints PASS / WARN / BLOCKED and JSON."""

from __future__ import annotations

import json
import os
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
        return {"status": "BLOCKED", "error": str(exc)}


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
        return {"status": "BLOCKED", "error": str(exc)}


def check_database() -> dict:
    try:
        from scripts.db.engine import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "PASS"}
    except Exception as exc:
        return {"status": "BLOCKED", "error": str(exc)}


def check_pgvector() -> dict:
    try:
        from scripts.db.engine import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            ext = conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")).scalar_one_or_none()
        return {"status": "PASS" if ext == "vector" else "BLOCKED", "extension": ext}
    except Exception as exc:
        return {"status": "BLOCKED", "error": str(exc)}


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
        return {"status": "BLOCKED", "error": str(exc)}


def check_memory() -> dict:
    try:
        from memory.retrieval import retrieve
        from memory.writeback import write_patterns
        retrieved = retrieve({"query": "doctor"})
        written = write_patterns({"kind": "doctor", "confidence": 0.1})
        ok = "historical_successful_patterns" in retrieved and written["written"] >= 1
        return {"status": "PASS" if ok else "BLOCKED"}
    except Exception as exc:
        return {"status": "BLOCKED", "error": str(exc)}


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
        return {"status": "BLOCKED", "error": str(exc)}


def check_lechuang() -> dict:
    from creative.providers.lechuang.adapter import LechuangAdapter
    adapter = LechuangAdapter()
    ready, reason = adapter.live_ready()
    auth = adapter.client.auth()
    return {
        "status": "PASS" if ready else "BLOCKED",
        "runtime": "PASS" if ready else "BLOCKED",
        "auth": "PASS" if auth.api_key_present else "BLOCKED",
        "image": "PASS" if ready else "BLOCKED",
        "video": "PASS" if ready else "BLOCKED",
        "reason": reason,
        "contract_verified": auth.contract_verified,
        "api_key_present": auth.api_key_present,
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
        return {"status": "BLOCKED", "error": str(exc)}



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
        ok = "lechuang" in resolver.providers and "mock" not in resolver.providers and social.implementation is not None
        return _status(ok, creative_providers=sorted(resolver.providers), social=social.name)
    except Exception as exc:
        return _status(False, error=str(exc))


def check_lechuang_contract() -> dict:
    from creative.providers.lechuang.client import CONTRACT_VERIFIED, LechuangClient
    from creative.providers.lechuang.schemas import CreateImageRequest, CreateTaskResponse, ProviderError
    client = LechuangClient()
    typed = all((CreateImageRequest, CreateTaskResponse, ProviderError))
    verified = bool(client.contract_verified and CONTRACT_VERIFIED and typed)
    if verified:
        return _status(True, reason=client.contract_reason, env="LECHUANG_API_URL", service="lechuang")
    return {"status": "BLOCKED_EXTERNAL", "reason": client.contract_reason, "env": "LECHUANG_API_URL", "service": "lechuang", "next": "Extract the official Lechuang HTTP contract from the operator workbench/docs. Do not guess endpoints."}


def check_lechuang_auth() -> dict:
    from creative.providers.lechuang.adapter import LechuangAdapter
    adapter = LechuangAdapter()
    auth = adapter.client.auth()
    if auth.api_key_present:
        return _status(True, reason="ok", env="LECHUANG_API_KEY")
    return {"status": "BLOCKED_EXTERNAL", "reason": "LECHUANG_API_KEY missing", "env": "LECHUANG_API_KEY", "next": "Put a real LECHUANG_API_KEY in the operator environment after the contract is verified."}


def check_lechuang_capability(name: str) -> dict:
    from creative.providers.lechuang.adapter import LechuangAdapter
    adapter = LechuangAdapter()
    ready, reason = adapter.live_ready()
    verified = adapter.has_verified(name)
    if ready and verified:
        return _status(True, reason=reason, capability=name, verified=verified, env="LECHUANG_API_KEY", service="lechuang")
    return {"status": "BLOCKED_EXTERNAL", "reason": reason, "capability": name, "verified": verified, "env": "LECHUANG_API_KEY", "service": "lechuang"}


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
    return ROOT / "docs/audits/meiti-v4.4.3-cn-e2e.json"


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
    creative = existing.get("creative") if isinstance(existing.get("creative"), dict) else {}
    distribution = existing.get("distribution") if isinstance(existing.get("distribution"), dict) else {}
    payload = {
        "version": "4.4.3",
        "overall": "READY" if all(item.get("status") == "PASS" for item in checks.values()) else "BLOCKED",
        "creative": {
            "workflow": creative.get("workflow") or "",
            "provider": creative.get("provider") or "",
            "image_asset_id": creative.get("image_asset_id") or "",
            "video_asset_id": creative.get("video_asset_id") or "",
            "judge": creative.get("judge") or "blocked",
            "reason": checks.get("Real Creative E2E", {}).get("reason"),
        },
        "distribution": {
            "provider": distribution.get("provider") or "",
            "account_id": distribution.get("account_id") or distribution.get("integration_id") or "",
            "remote_post_id": distribution.get("remote_post_id") or "",
            "status": distribution.get("status") or "blocked",
            "reason": checks.get("Real Distribution E2E", {}).get("reason"),
        },
        "reconciliation": existing.get("reconciliation") or {"status": "blocked"},
        "analytics": existing.get("analytics") or {"ingested": False},
        "memory": existing.get("memory") or {"written": False},
        "blockers": [
            {"check": name, "reason": value.get("reason") or value.get("error"), "env": value.get("env"), "service": value.get("service"), "next": value.get("next")}
            for name, value in checks.items()
            if value.get("status") != "PASS"
        ],
    }
    path = e2e_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return payload


def check_real_creative_e2e() -> dict:
    data = load_e2e()
    creative = data.get("creative") or {}
    image = str(creative.get("image_asset_id") or "").strip()
    video = str(creative.get("video_asset_id") or "").strip()
    judge = str(creative.get("judge") or "").lower()
    ok = bool(image and video and judge == "pass" and not image.startswith("fake") and not video.startswith("fake"))
    if ok:
        return _status(True, reason="ok", env="LECHUANG_API_KEY", service="lechuang")
    return {"status": "BLOCKED_EXTERNAL", "reason": "no real creative E2E evidence", "env": "LECHUANG_API_KEY", "service": "lechuang", "next": "After the Lechuang contract is verified, run one image and one image-to-video workflow and persist real asset IDs."}


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
    lechuang_auth = check_lechuang_auth()
    lechuang_contract = check_lechuang_contract()
    social = social_doctor.run()
    return {
        "Architecture": check_architecture(),
        "Persistence": check_database(),
        "Credential": social["Credential Store"],
        "Creative Runtime": check_creative_runtime(),
        "Lechuang": social["Lechuang"],
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
        "Image-to-Video": check_lechuang_capability("image_to_video"),
        "Video Generation": check_lechuang_capability("text_to_video"),
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
    }


def as_payload(checks: dict) -> dict:
    statuses = {key: value.get("status") for key, value in checks.items()}
    code_blocked = [name for name, status in statuses.items() if status not in {"PASS", "HANDOFF_ONLY", "NOT_APPLICABLE", "BLOCKED_EXTERNAL"}]
    external = [name for name, status in statuses.items() if status == "BLOCKED_EXTERNAL"]
    return {"ready": not code_blocked and not external, "architecture_ready": not code_blocked, "checks": statuses, "details": checks}


def main() -> int:
    checks = run()
    audit = write_e2e_audit(checks)
    payload = as_payload(checks)
    for name, status in payload["checks"].items():
        print(f"{name}: {status}")
    print("Overall:", "READY" if payload["ready"] else "BLOCKED")
    print(json.dumps({"ready": payload["ready"], "overall": audit.get("overall"), "checks": payload["checks"], "blockers": audit.get("blockers")}, default=str))
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
