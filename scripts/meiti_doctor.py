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
    legacy = (ROOT / "workspaces").exists()
    return {"status": "BLOCKED" if missing or legacy else "PASS", "missing": missing, "legacy_workspaces": legacy}


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
        return {
            "status": "PASS" if "postiz" in registry and not enabled_from_yaml else "BLOCKED",
            "providers": sorted(registry),
            "enabled": enabled_from_yaml,
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
    from governance.distribution_gate import check_distribution_job
    from integrations.contracts.distribution import ContentVariant, DistributionJob, Integration, IntegrationCapabilities
    integration = Integration("i", "x", "a", "global", IntegrationCapabilities(publish=True), "postiz", "postiz", True, state="ENABLED")
    job = DistributionJob("j", "p", "i", ContentVariant("i", "test"))
    failures = check_distribution_job(
        job, integration, content_valid=True, evidence_valid=True, account_valid=True,
        media_valid=True, approval_valid=False, provider_verified=True, integration_verified=True,
        capability_verified=True, idempotency_valid=True, media_uploaded=True, payload_valid=True,
    )
    return {"status": "PASS" if failures == ["approval invalid"] else "BLOCKED", "failures": failures}


_POSTIZ_CACHE = None


def check_postiz() -> dict:
    global _POSTIZ_CACHE
    if _POSTIZ_CACHE is not None:
        return dict(_POSTIZ_CACHE)
    from integrations.providers.postiz.client import PostizClient
    from integrations.providers.postiz.errors import PostizClientError
    client = PostizClient(timeout=2.0, max_attempts=1)
    key_missing = not os.getenv("POSTIZ_API_KEY", "").strip()
    try:
        health = client.health()
        payload = {
            "status": "PASS" if health.authenticated else "BLOCKED",
            "health": health.__dict__,
            "reason": None if health.authenticated else ("POSTIZ_API_KEY missing" if key_missing else "not authenticated"),
            "reachable": health.reachable,
            "authenticated": health.authenticated,
            "account_count": health.account_count,
        }
    except PostizClientError as exc:
        payload = {
            "status": "BLOCKED",
            "error": str(exc),
            "reason": "POSTIZ_API_KEY missing" if key_missing else str(exc),
            "reachable": False,
            "authenticated": False,
            "account_count": 0,
        }
    if key_missing:
        payload["status"] = "BLOCKED"
        payload["reason"] = "POSTIZ_API_KEY missing"
    _POSTIZ_CACHE = payload
    return dict(payload)


def check_postiz_integrations() -> dict:
    postiz = check_postiz()
    if postiz.get("status") != "PASS":
        return {"status": "BLOCKED", "reason": postiz.get("reason") or postiz.get("error")}
    count = int(postiz.get("account_count") or 0)
    return {"status": "PASS" if count else "BLOCKED", "account_count": count}


def check_postiz_capabilities() -> dict:
    postiz = check_postiz()
    if postiz.get("status") != "PASS":
        return {"status": "BLOCKED", "reason": postiz.get("reason") or postiz.get("error")}
    return {"status": "PASS" if postiz.get("authenticated") else "BLOCKED"}


def check_research() -> dict:
    from intelligence.router import credential_state
    state = credential_state()
    return {"status": "PASS" if state.available else "BLOCKED", "available": state.available}


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
        "auth": "PASS" if auth.api_key_present and ready else "BLOCKED",
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


def run() -> dict:
    postiz = check_postiz()
    workers = check_workers()
    lechuang = check_lechuang()
    return {
        "Repository": check_repository(),
        "Database": check_database(),
        "pgvector": check_pgvector(),
        "Embedding": check_embedding(),
        "Knowledge Graph": check_kg(),
        "Agent Registry": check_agents(),
        "Provider Registry": check_provider_registry(),
        "Postiz": postiz,
        "Postiz authentication": {"status": postiz.get("status"), "reason": postiz.get("reason")},
        "Postiz integrations": check_postiz_integrations(),
        "Postiz capabilities": check_postiz_capabilities(),
        "Research": check_research(),
        "Scheduler": workers,
        "Workers": workers,
        "Creative Workflow Engine": check_creative_engine(),
        "Lechuang": lechuang,
        "Lechuang authentication": {"status": lechuang.get("auth"), "reason": lechuang.get("reason")},
        "Lechuang capabilities": {"status": "PASS" if lechuang.get("contract_verified") else "BLOCKED"},
        "Analytics": check_analytics(),
        "Memory": check_memory(),
        "Publish Gate": check_gate(),
        "Control Plane": check_control_plane(),
    }


def as_payload(checks: dict) -> dict:
    statuses = {key: value.get("status") for key, value in checks.items()}
    blocked = [name for name, status in statuses.items() if status == "BLOCKED"]
    return {"ready": not blocked, "checks": statuses, "details": checks}


def main() -> int:
    checks = run()
    payload = as_payload(checks)
    for name, status in payload["checks"].items():
        print(f"{name}: {status}")
    print("OVERALL:", "PASS" if payload["ready"] else "BLOCKED")
    print(json.dumps({"ready": payload["ready"], "checks": payload["checks"]}, default=str))
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
