#!/usr/bin/env python3
"""Meiti CLI: CN social accounts, connect, verify, enable, publish."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _runtime(*, testing: bool = False):
    from social.runtime.container import SocialRuntime
    if testing:
        return SocialRuntime.testing()
    return SocialRuntime.production()


def _manager():
    return _runtime().manager


def cmd_accounts(_args: argparse.Namespace) -> int:
    rows = _manager().doctor_rows()
    if not rows:
        print("no social accounts")
        return 0
    for row in rows:
        print(f"{row['label']}: {row['status']} ACTION: {row['action']}")
    return 0


def cmd_connect(args: argparse.Namespace) -> int:
    runtime = _runtime()
    authorization = {}
    if args.code:
        authorization["code"] = args.code
    if args.username:
        authorization["username"] = args.username
        authorization["account_id"] = args.account_id or f"{args.platform}:{args.username}"
    account = runtime.manager.connect_account(args.platform, authorization=authorization or None)
    print(f"{account.label()}: {account.status} id={account.account_id}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    manager = _manager()
    if args.account_id:
        account = manager.verify_account(args.account_id)
        print(f"{account.label()}: {account.status}")
        return 0
    for account in manager.list_accounts():
        verified = manager.verify_account(account.account_id)
        print(f"{verified.label()}: {verified.status}")
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    account = _manager().enable_account(args.account_id)
    print(f"{account.label()}: {account.status}")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    account = _manager().refresh_account(args.account_id)
    print(f"{account.label()}: {account.status}")
    return 0


def cmd_disconnect(args: argparse.Namespace) -> int:
    account = _manager().disconnect_account(args.account_id)
    print(f"{account.label()}: {account.status}")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    runtime = _runtime()
    from content.models import ContentPackage
    package = ContentPackage(
        args.package_id or "cli-package",
        args.title or "Meiti post",
        args.body or "",
        media_assets=tuple(args.media or ()),
        commerce_intent=args.commerce_intent or "none",
        metadata={"approval": "approved", "price": args.price, "category_id": args.category_id},
    )
    agent = runtime.agent()
    job = agent.create_job(package, platform=args.platform, job_id=args.job_id or "cli-job", account_id=args.account_id)
    result = agent.execute(job)
    kind = getattr(result, "kind", "")
    if kind == "handoff" or hasattr(result, "handoff"):
        handoff = getattr(result, "handoff", result)
        payload = {
            "kind": "handoff",
            "handoff_id": getattr(handoff, "handoff_id", ""),
            "status": getattr(handoff, "status", ""),
            "platform": getattr(handoff, "platform", "xiaohongshu"),
        }
        print("READY_FOR_XHS")
        print(json.dumps(payload))
        return 0
    if kind == "listing" or hasattr(result, "listing"):
        listing = getattr(result, "listing", result)
        payload = {
            "kind": "listing",
            "listing_id": getattr(listing, "listing_id", ""),
            "provider_item_id": getattr(listing, "provider_item_id", ""),
            "status": getattr(listing, "status", ""),
            "provider_request_id": getattr(result, "provider_request_id", None),
        }
        print(json.dumps(payload))
        return 0
    publication = getattr(result, "publication", result)
    payload = {
        "kind": "publication",
        "publication_id": getattr(publication, "publication_id", ""),
        "provider_post_id": getattr(publication, "provider_post_id", ""),
        "status": getattr(publication, "status", ""),
        "platform": getattr(publication, "platform", ""),
        "provider_object_type": getattr(publication, "provider_object_type", ""),
        "provider_request_id": getattr(result, "provider_request_id", None),
        "provider_object_id": getattr(result, "provider_object_id", ""),
    }
    print(json.dumps(payload))
    return 0



def bootstrap_production() -> dict:
    """Pure preflight. Never write tokens, API keys, credentials, or accounts."""
    import os
    import stat
    from pathlib import Path as _Path

    checks: dict = {}

    def _item(status: str, **extra):
        payload = {"status": status}
        payload.update(extra)
        return payload

    secret_dir = os.environ.get("MEITI_SECRET_DIR", "").strip()
    if not secret_dir:
        checks["secret_dir"] = _item("BLOCKED_EXTERNAL", reason="MEITI_SECRET_DIR missing")
    else:
        path = _Path(secret_dir)
        if not path.is_dir():
            checks["secret_dir"] = _item("BLOCKED_EXTERNAL", reason="MEITI_SECRET_DIR does not exist", path=str(path))
        else:
            try:
                mode = stat.S_IMODE(path.stat().st_mode)
                if mode != 0o700:
                    checks["secret_dir"] = _item("FAIL", reason=f"directory mode {oct(mode)} != 0700", path=str(path))
                else:
                    checks["secret_dir"] = _item("PASS", path=str(path), mode=oct(mode))
            except OSError as exc:
                checks["secret_dir"] = _item("FAIL", reason=str(exc))

    try:
        from scripts.db.engine import engine
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        checks["database"] = _item("PASS")
    except Exception as exc:
        checks["database"] = _item("BLOCKED_EXTERNAL", reason=str(exc))

    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from scripts.db.engine import engine
        from scripts.db.migrate import MIGRATIONS_DIR
        cfg = Config()
        cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
        script = ScriptDirectory.from_config(cfg)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current = context.get_current_revision()
        head = script.get_current_head()
        if current == head:
            checks["migration"] = _item("PASS", current=current, head=head)
        else:
            checks["migration"] = _item("FAIL", current=current, head=head, reason="database is not at head revision")
    except Exception as exc:
        checks["migration"] = _item("BLOCKED_EXTERNAL", reason=str(exc))

    def _env(keys: tuple[str, ...]) -> bool:
        return all(os.getenv(key, "").strip() for key in keys)

    checks["douyin_oauth"] = _item("PASS" if _env(("DOUYIN_CLIENT_KEY", "DOUYIN_CLIENT_SECRET", "DOUYIN_REDIRECT_URI")) else "BLOCKED_EXTERNAL")
    checks["kuaishou_oauth"] = _item("PASS" if _env(("KUAISHOU_APP_ID", "KUAISHOU_APP_SECRET", "KUAISHOU_REDIRECT_URI")) else "BLOCKED_EXTERNAL")
    checks["xianyu_oauth"] = _item("PASS" if _env(("XIANYU_APP_KEY", "XIANYU_APP_SECRET", "XIANYU_REDIRECT_URI")) else "BLOCKED_EXTERNAL")
    jushita = (os.getenv("MEITI_XIANYU_DEPLOYMENT_MODE") or "").strip().upper() == "JUSHITA"
    checks["xianyu_jushita"] = _item("PASS" if jushita else "BLOCKED_EXTERNAL")
    checks["xhs_oauth"] = _item("PASS" if _env(("XHS_CLIENT_ID", "XHS_CLIENT_SECRET", "XHS_REDIRECT_URI")) else "BLOCKED_EXTERNAL")
    checks["lechuang"] = _item("PASS" if _env(("LECHUANG_API_URL", "LECHUANG_API_KEY")) else "BLOCKED_EXTERNAL")

    try:
        from social.runtime.container import SocialRuntime
        runtime_ok = callable(getattr(SocialRuntime, "production", None))
        checks["runtime"] = _item("PASS" if runtime_ok else "FAIL")
    except Exception as exc:
        checks["runtime"] = _item("FAIL", reason=str(exc))

    blocking = [name for name, item in checks.items() if item["status"] == "FAIL"]
    external = [name for name, item in checks.items() if item["status"] == "BLOCKED_EXTERNAL"]
    if blocking:
        overall, exit_code = "FAIL", 1
    elif external:
        overall, exit_code = "BLOCKED_EXTERNAL", 1
    else:
        overall, exit_code = "PASS", 0
    return {
        "overall": {"status": overall},
        "checks": checks,
        "generated_credentials": False,
        "credential_writes": False,
        "exit_code": exit_code,
    }


def cmd_doctor(_args: argparse.Namespace) -> int:
    from scripts.social_doctor import main
    return main()


def cmd_bootstrap_production(_args: argparse.Namespace) -> int:
    report = bootstrap_production()
    print(json.dumps(report, indent=2, default=str))
    return int(report.get("exit_code") or 1)


def cmd_credentials_put(args: argparse.Namespace) -> int:
    """Explicit credential provisioning. Bootstrap never writes secrets."""
    import os
    from social.auth.secrets import production_secret_store, secret_id

    if args.provider != "lechuang":
        print(f"unsupported provider: {args.provider}")
        return 1
    key = os.getenv("LECHUANG_API_KEY", "").strip()
    url = os.getenv("LECHUANG_API_URL", "").strip()
    if not key or not url:
        print('{"overall": {"status": "BLOCKED_EXTERNAL"}, "reason": "LECHUANG_API_URL/LECHUANG_API_KEY missing"}')
        return 1
    store = production_secret_store()
    store.put_json({"api_key": key, "api_url": url}, ref=secret_id("lechuang", "api"))
    print('{"provider": "lechuang", "status": "STORED"}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="meiti")
    sub = parser.add_subparsers(dest="group", required=True)
    boot = sub.add_parser("bootstrap-production")
    boot.set_defaults(func=cmd_bootstrap_production)
    cred = sub.add_parser("credentials")
    cred_sub = cred.add_subparsers(dest="command", required=True)
    put = cred_sub.add_parser("put")
    put.add_argument("--provider", required=True, choices=("lechuang",))
    put.set_defaults(func=cmd_credentials_put)
    social = sub.add_parser("social")
    social_sub = social.add_subparsers(dest="command", required=True)
    social_sub.add_parser("accounts").set_defaults(func=cmd_accounts)
    connect = social_sub.add_parser("connect")
    connect.add_argument("platform")
    connect.add_argument("--code")
    connect.add_argument("--username")
    connect.add_argument("--account-id")
    connect.set_defaults(func=cmd_connect)
    verify = social_sub.add_parser("verify")
    verify.add_argument("account_id", nargs="?")
    verify.set_defaults(func=cmd_verify)
    enable = social_sub.add_parser("enable")
    enable.add_argument("account_id")
    enable.set_defaults(func=cmd_enable)
    refresh = social_sub.add_parser("refresh")
    refresh.add_argument("account_id")
    refresh.set_defaults(func=cmd_refresh)
    disconnect = social_sub.add_parser("disconnect")
    disconnect.add_argument("account_id")
    disconnect.set_defaults(func=cmd_disconnect)
    publish = social_sub.add_parser("publish")
    publish.add_argument("--platform", required=True)
    publish.add_argument("--body", default="")
    publish.add_argument("--title", default="")
    publish.add_argument("--package-id")
    publish.add_argument("--job-id")
    publish.add_argument("--account-id")
    publish.add_argument("--media", nargs="*")
    publish.add_argument("--commerce-intent", default="none")
    publish.add_argument("--price")
    publish.add_argument("--category-id")
    publish.set_defaults(func=cmd_publish)
    social_sub.add_parser("doctor").set_defaults(func=cmd_doctor)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
