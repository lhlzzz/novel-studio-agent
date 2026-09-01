"""Meiti Control Plane: one snapshot of runtime subsystems."""

from __future__ import annotations

from typing import Any


def snapshot() -> dict[str, Any]:
    from agents.registry import list_agents
    from integrations.registry.loader import load_registry
    from intelligence.router import credential_state

    agents = []
    for handle in list_agents():
        agents.append({
            "name": handle.name,
            "owner": handle.owner,
            "status": handle.status,
            "capabilities": list(handle.capabilities),
            "implementation": type(handle.implementation).__name__,
        })
    registry = load_registry()
    integrations = []
    for item in registry.values():
        integrations.append({
            "id": item.id,
            "provider": item.provider,
            "enabled": item.enabled,
            "state": item.state,
            "adapter": item.adapter,
        })
    database = _database()
    workers = {
        "scheduler": "services.workers.scheduler",
        "reconciliation": "services.workers.reconciliation_worker",
        "analytics": "services.workers.analytics_worker",
        "creative": "services.workers.creative_worker",
        "queue": "services.queue",
    }
    research = credential_state()
    creative = _creative()
    providers = sorted({item["provider"] for item in integrations} | set(creative.get("providers") or []))
    return {
        "agents": agents,
        "integrations": integrations,
        "accounts": [item for item in integrations if item["enabled"]],
        "providers": providers,
        "jobs": database.get("jobs", []),
        "failures": database.get("failures", []),
        "analytics": database.get("analytics", []),
        "research": {"available": research.available, "authenticated": research.authenticated},
        "workers": workers,
        "database": {"ok": database.get("ok", False), "error": database.get("error")},
        "creative_runs": creative.get("runs", []),
        "creative_tasks": creative.get("tasks", []),
        "assets": creative.get("assets", []),
        "judges": creative.get("judges", []),
    }


def _database() -> dict[str, Any]:
    try:
        from scripts.db.engine import SessionLocal
        from scripts.db.models import AgentRecord
        from sqlalchemy import func

        with SessionLocal() as session:
            jobs = session.query(func.count(AgentRecord.id)).filter_by(record_type="distribution_job").scalar() or 0
            failures = session.query(func.count(AgentRecord.id)).filter_by(record_type="distribution_attempt").scalar() or 0
            analytics = session.query(func.count(AgentRecord.id)).filter_by(record_type="metric_snapshot").scalar() or 0
        return {"ok": True, "jobs": jobs, "failures": failures, "analytics": analytics}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "jobs": [], "failures": [], "analytics": []}


def _creative() -> dict[str, Any]:
    try:
        from creative.providers.lechuang.adapter import LechuangAdapter
        from creative.store import CreativeStore
        store = CreativeStore.production()
        adapter = LechuangAdapter()
        ready, reason = adapter.live_ready()
        return {
            "runs": store.list_runs(),
            "tasks": [item for run in store.list_runs() for item in store.list_tasks(run.run_id)],
            "assets": store.list_assets(),
            "judges": [{"name": "vision", "ready": ready, "reason": reason}],
            "providers": ["lechuang", "postiz"],
        }
    except Exception as exc:
        return {"runs": [], "tasks": [], "assets": [], "judges": [{"name": "vision", "ready": False, "reason": str(exc)}], "providers": ["lechuang"]}
