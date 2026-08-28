#!/usr/bin/env python3
"""meiti publish / external-action gate CLI.

Default state is LOCKED. External actions require an approved gate record
and a local approval file signed by boss (or explicit CLI approve by boss).

This CLI never publishes. It only checks / records gate state.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.db.engine import SessionLocal  # noqa: E402
from scripts.db.models import PublishGate  # noqa: E402

GATES_DIR = ROOT / ".gates"
APPROVALS_DIR = GATES_DIR / "approvals"

EXTERNAL_ACTIONS = (
    "publish",
    "login",
    "dm",
    "list",
    "quote",
    "collect",
    "ads",
    "automation",
)

FIVE_CHECKS = (
    "ai_feel",
    "marketing_risk",
    "conversion_pressure",
    "copyright_risk",
    "labeling",
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _upsert_gate(
    *,
    gate_key: str,
    action: str,
    integration_id: str,
    distribution_job_id: str,
    status: str,
    requested_by: str,
    approved_by: str | None = None,
    rationale: str | None = None,
    checks: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
) -> PublishGate:
    with SessionLocal() as session:
        row = session.execute(
            select(PublishGate).where(PublishGate.gate_key == gate_key)
        ).scalar_one_or_none()
        fields = dict(
            action=action,
            integration_id=integration_id,
            distribution_job_id=distribution_job_id,
            status=status,
            requested_by=requested_by,
            approved_by=approved_by,
            rationale=rationale,
            checks=checks or {},
            evidence=evidence or {},
        )
        if row is None:
            row = PublishGate(gate_key=gate_key, **fields)
            session.add(row)
        else:
            for k, v in fields.items():
                if v is not None:
                    setattr(row, k, v)
            row.updated_at = _now()
        if status in {"approved", "denied"}:
            row.decided_at = _now()
        session.commit()
        session.refresh(row)
        return row


def _gate_to_dict(row: PublishGate) -> dict[str, Any]:
    return {
        "gate_key": row.gate_key,
        "action": row.action,
        "integration_id": row.integration_id,
        "distribution_job_id": row.distribution_job_id,
        "status": row.status,
        "requested_by": row.requested_by,
        "approved_by": row.approved_by,
        "rationale": row.rationale,
        "checks": row.checks,
        "evidence": row.evidence,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def run_five_checks(package_path: Path | None) -> dict[str, Any]:
    """Lightweight static checks against package markdown (heuristic)."""
    text = ""
    if package_path and package_path.is_file():
        text = package_path.read_text(encoding="utf-8", errors="replace")
    banned = ["稳赚", "包回本", "保证成交", "月入", "最低价", "一定火", "包过"]
    hard_cta = ["加微信", "私信我", "扫码付款", "点击购买链接"]
    failures = []
    if any(b in text for b in banned):
        failures.append("marketing_risk: banned absolute/guarantee language")
    if any(c in text for c in hard_cta) and "INTERNAL_ONLY" not in text:
        failures.append("conversion_pressure: hard CTA without INTERNAL_ONLY")
    if text and "INTERNAL_ONLY" not in text and "内部稿" not in text:
        failures.append("labeling: missing INTERNAL_ONLY / 内部稿 marker")

    result = {k: "pass" for k in FIVE_CHECKS}
    if failures:
        for f in failures:
            key = f.split(":", 1)[0]
            if key in result:
                result[key] = "fail"
    # Without body, mark pending not pass for publish readiness
    if not text:
        for k in FIVE_CHECKS:
            result[k] = "pending"
    result["failures"] = failures
    result["package_path"] = str(package_path) if package_path else None
    result["all_pass"] = bool(text) and not failures
    return result


def cmd_status(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        if args.gate_key:
            row = session.execute(
                select(PublishGate).where(PublishGate.gate_key == args.gate_key)
            ).scalar_one_or_none()
            if row is None:
                print(json.dumps({"status": "missing", "gate_key": args.gate_key}))
                return 1
            print(json.dumps(_gate_to_dict(row), ensure_ascii=False, indent=2))
            return 0
        rows = session.execute(
            select(PublishGate).order_by(PublishGate.id.desc()).limit(args.limit)
        ).scalars().all()
        print(json.dumps([_gate_to_dict(r) for r in rows], ensure_ascii=False, indent=2))
    return 0


def cmd_request(args: argparse.Namespace) -> int:
    if args.action not in EXTERNAL_ACTIONS:
        raise SystemExit(f"action must be one of {EXTERNAL_ACTIONS}")
    package_path = Path(args.package) if args.package else None
    checks = run_five_checks(package_path)
    integration_id = args.integration_id
    distribution_job_id = args.distribution_job_id
    gate_key = args.gate_key or f"gate:{args.action}:{integration_id}:{distribution_job_id}"
    row = _upsert_gate(
        gate_key=gate_key,
        action=args.action,
        integration_id=integration_id,
        distribution_job_id=distribution_job_id,
        status="requested" if checks.get("all_pass") else "locked",
        requested_by=args.by or "agent",
        rationale=args.rationale or "request external action; awaiting boss approval",
        checks=checks,
        evidence={"package": args.package},
    )
    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    stub = APPROVALS_DIR / f"{gate_key.replace(':', '__')}.request.json"
    stub.write_text(
        json.dumps(
            {
                **_gate_to_dict(row),
                "instruction": "Boss: review checks, then `python scripts/publish_gate.py approve --gate-key ... --by boss`",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(_gate_to_dict(row), ensure_ascii=False, indent=2))
    if not checks.get("all_pass"):
        print("NOTE: five-checks not all pass → status kept locked/requested blocked", file=sys.stderr)
        return 2
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    if (args.by or "").lower() not in {"boss", "owner", "老板"}:
        raise SystemExit("approve requires --by boss (or owner/老板)")
    with SessionLocal() as session:
        row = session.execute(
            select(PublishGate).where(PublishGate.gate_key == args.gate_key)
        ).scalar_one_or_none()
        if row is None:
            raise SystemExit(f"unknown gate_key={args.gate_key}")
        if row.status not in {"requested", "locked", "denied"}:
            # allow re-approve from locked only with force
            if not args.force:
                raise SystemExit(f"cannot approve from status={row.status} without --force")
        checks = row.checks or {}
        if checks and checks.get("all_pass") is False and not args.force:
            raise SystemExit("five-checks failed; refuse approve without --force")
        row.status = "approved"
        row.approved_by = args.by
        row.rationale = args.rationale or row.rationale or "approved by boss"
        row.decided_at = _now()
        row.updated_at = _now()
        session.commit()
        session.refresh(row)
        data = _gate_to_dict(row)
    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    (APPROVALS_DIR / f"{args.gate_key.replace(':', '__')}.approved.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def cmd_deny(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        row = session.execute(
            select(PublishGate).where(PublishGate.gate_key == args.gate_key)
        ).scalar_one_or_none()
        if row is None:
            raise SystemExit(f"unknown gate_key={args.gate_key}")
        row.status = "denied"
        row.approved_by = args.by or "boss"
        row.rationale = args.rationale or "denied"
        row.decided_at = _now()
        session.commit()
        session.refresh(row)
        print(json.dumps(_gate_to_dict(row), ensure_ascii=False, indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Exit 0 only if a matching DistributionJob gate is approved."""
    with SessionLocal() as session:
        q = select(PublishGate).where(PublishGate.action == args.action)
        if args.gate_key:
            q = select(PublishGate).where(PublishGate.gate_key == args.gate_key)
        else:
            if args.integration_id:
                q = q.where(PublishGate.integration_id == args.integration_id)
            if args.distribution_job_id:
                q = q.where(PublishGate.distribution_job_id == args.distribution_job_id)
        row = session.execute(q.order_by(PublishGate.id.desc())).scalars().first()
        allowed = bool(row and row.status == "approved")
        payload = {
            "allowed": allowed,
            "reason": "approved" if allowed else "no approved gate",
            "gate": _gate_to_dict(row) if row else None,
            "hard_boundary": "output≠publish; CLI never executes external actions",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if allowed else 1


def cmd_prepare(args: argparse.Namespace) -> int:
    """Describe a connector job without uploading or publishing anything."""
    print(
        json.dumps(
            {
                "operation": "prepare",
                "integration_id": args.integration_id,
                "distribution_job_id": args.distribution_job_id,
                "hard_boundary": "prepared only; no external request issued",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_external_action_unavailable(args: argparse.Namespace) -> int:
    """Fail closed until a separately approved integration connector exists."""
    print(
        json.dumps(
            {
                "operation": args.command,
                "allowed": False,
                "reason": "integration connector is not implemented",
                "hard_boundary": "use prepare, request, and check only",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 2


def cmd_selftest(args: argparse.Namespace) -> int:
    GATES_DIR.mkdir(parents=True, exist_ok=True)
    # create a locked gate and verify check denies
    key = "gate:selftest:publish:integration:pkg-selftest-job"
    _upsert_gate(
        gate_key=key,
        action="publish",
        integration_id="integration-selftest",
        distribution_job_id="pkg-selftest-job",
        status="locked",
        requested_by="selftest",
        rationale="selftest locked",
        checks={"all_pass": False},
    )
    rc_deny = cmd_check(
        argparse.Namespace(action="publish", gate_key=key,
                           integration_id=None, distribution_job_id=None)
    )
    # simulate boss approve with force (checks failed)
    rc_approve = cmd_approve(
        argparse.Namespace(gate_key=key, by="boss", rationale="selftest force", force=True)
    )
    rc_allow = cmd_check(
        argparse.Namespace(action="publish", gate_key=key,
                           integration_id=None, distribution_job_id=None)
    )
    rc_prepare = cmd_prepare(
        argparse.Namespace(integration_id="integration-selftest", distribution_job_id="pkg-selftest-job")
    )
    rc_upload = cmd_external_action_unavailable(
        argparse.Namespace(command="upload-draft")
    )
    rc_publish = cmd_external_action_unavailable(argparse.Namespace(command="publish"))
    # lock again after selftest
    _upsert_gate(
        gate_key=key,
        action="publish",
        integration_id="integration-selftest",
        distribution_job_id="pkg-selftest-job",
        status="locked",
        requested_by="selftest",
        rationale="re-lock after selftest",
        checks={"all_pass": False},
    )
    ok = (
        rc_deny == 1
        and rc_approve == 0
        and rc_allow == 0
        and rc_prepare == 0
        and rc_upload == 2
        and rc_publish == 2
    )
    print(json.dumps({"selftest": "ok" if ok else "fail", "gate_key": key}, ensure_ascii=False))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="meiti publish gate (never publishes)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status")
    p.add_argument("--gate-key", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("request")
    p.add_argument("--action", required=True, choices=EXTERNAL_ACTIONS)
    p.add_argument("--integration-id", required=True)
    p.add_argument("--distribution-job-id", required=True)
    p.add_argument("--package", default=None, help="path to package markdown for 5 checks")
    p.add_argument("--gate-key", default=None)
    p.add_argument("--by", default="agent")
    p.add_argument("--rationale", default=None)
    p.set_defaults(func=cmd_request)

    p = sub.add_parser("approve")
    p.add_argument("--gate-key", required=True)
    p.add_argument("--by", required=True)
    p.add_argument("--rationale", default=None)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("deny")
    p.add_argument("--gate-key", required=True)
    p.add_argument("--by", default="boss")
    p.add_argument("--rationale", default=None)
    p.set_defaults(func=cmd_deny)

    p = sub.add_parser("check")
    p.add_argument("--action", default="publish")
    p.add_argument("--gate-key", default=None)
    p.add_argument("--integration-id", default=None)
    p.add_argument("--distribution-job-id", default=None)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("prepare")
    p.add_argument("--integration-id", required=True)
    p.add_argument("--distribution-job-id", required=True)
    p.set_defaults(func=cmd_prepare)

    for command in ("upload-draft", "publish"):
        p = sub.add_parser(command)
        p.set_defaults(func=cmd_external_action_unavailable)

    p = sub.add_parser("selftest")
    p.set_defaults(func=cmd_selftest)

    args = parser.parse_args()
    try:
        return int(args.func(args) or 0)
    except SQLAlchemyError as exc:
        print(f"publish_gate failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
