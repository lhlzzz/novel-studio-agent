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
    return {
        "agents": agents,
        "integrations": integrations,
        "accounts": [item for item in integrations if item["enabled"]],
        "providers": sorted({item["provider"] for item in integrations}),
        "jobs": database.get("jobs", []),
        "failures": database.get("failures", []),
        "analytics": database.get("analytics", []),
        "research": {"available": research.available, "authenticated": research.authenticated},
        "workers": workers,
        "database": {"ok": database.get("ok", False), "error": database.get("error")},
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
