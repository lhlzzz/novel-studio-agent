#!/usr/bin/env python3
"""Meiti CLI: social accounts, verify, disconnect, publish."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _manager():
    from social.accounts.manager import SocialAccountManager

    return SocialAccountManager()


def cmd_accounts(_args: argparse.Namespace) -> int:
    manager = _manager()
    rows = manager.doctor_rows()
    if not rows:
        print("no social accounts")
        return 0
    for row in rows:
        print(f"{row['label']}: {row['status']} ACTION: {row['action']}")
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


def cmd_disconnect(args: argparse.Namespace) -> int:
    account = _manager().disconnect_account(args.account_id)
    print(f"{account.label()}: {account.status}")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    from agents.distribution_agent import DistributionAgent
    from content.models import ContentPackage

    agent = DistributionAgent()
    package = ContentPackage(args.package_id or "cli-package", args.title or "Meiti post", args.body)
    job = agent.create_job(package, platform=args.platform, job_id=args.job_id or "cli-job")
    publication = agent.execute(
        job,
        content_valid=True,
        evidence_valid=True,
        account_valid=True,
        media_valid=True,
        approval_valid=True,
        provider_verified=True,
        account_verified=True,
        capability_verified=True,
        idempotency_valid=True,
        media_uploaded=True,
        payload_valid=True,
    )
    print(json.dumps({
        "publication_id": publication.publication_id,
        "provider_post_id": publication.provider_post_id,
        "status": publication.status,
        "platform": publication.platform,
    }))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="meiti")
    sub = parser.add_subparsers(dest="group", required=True)
    social = sub.add_parser("social")
    social_sub = social.add_subparsers(dest="command", required=True)
    social_sub.add_parser("accounts").set_defaults(func=cmd_accounts)
    verify = social_sub.add_parser("verify")
    verify.add_argument("account_id", nargs="?")
    verify.set_defaults(func=cmd_verify)
    disconnect = social_sub.add_parser("disconnect")
    disconnect.add_argument("account_id")
    disconnect.set_defaults(func=cmd_disconnect)
    publish = social_sub.add_parser("publish")
    publish.add_argument("--platform", default="x")
    publish.add_argument("--body", default="MEITI SOCIAL PUBLISH")
    publish.add_argument("--title", default="")
    publish.add_argument("--package-id")
    publish.add_argument("--job-id")
    publish.set_defaults(func=cmd_publish)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
