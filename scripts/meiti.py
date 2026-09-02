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
    agent = runtime.agent(provider_name=args.platform)
    job = agent.create_job(package, platform=args.platform, job_id=args.job_id or "cli-job", account_id=args.account_id)
    result = agent.execute(job)
    if hasattr(result, "handoff_id"):
        payload = {
            "handoff_id": result.handoff_id,
            "status": result.status,
            "platform": result.platform,
            "kind": "handoff",
        }
        print("READY_FOR_XHS")
        print(json.dumps(payload))
        return 0
    payload = {
        "publication_id": result.publication_id,
        "provider_post_id": result.provider_post_id,
        "status": result.status,
        "platform": result.platform,
        "provider_object_type": result.provider_object_type,
    }
    print(json.dumps(payload))
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    from scripts.social_doctor import main
    return main()


def main() -> int:
    parser = argparse.ArgumentParser(prog="meiti")
    sub = parser.add_subparsers(dest="group", required=True)
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
