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
        print(
            f"provider={row.get('provider') or ''} account_id={row.get('account_id') or ''} "
            f"status={row['status']} ACTION: {row['action']}"
        )
    return 0


def cmd_connect(args: argparse.Namespace) -> int:
    runtime = _runtime()
    authorization = {}
    if args.code:
        authorization["code"] = args.code
    if getattr(args, "state", None):
        authorization["state"] = args.state
    if args.username:
        authorization["username"] = args.username
        authorization["account_id"] = args.account_id or f"{args.platform}:{args.username}"
    account = runtime.manager.connect_account(args.platform, authorization=authorization or None)
    print(f"provider={account.provider} account_id={account.account_id} status={account.status}")
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


def _provider_redirect(provider: str) -> str:
    import os
    names = {
        "douyin": "DOUYIN_REDIRECT_URI",
        "kuaishou": "KUAISHOU_REDIRECT_URI",
        "xianyu": "XIANYU_REDIRECT_URI",
        "xiaohongshu": "XHS_REDIRECT_URI",
    }
    return os.getenv(names.get(provider, ""), "").strip()


def cmd_oauth_start(args: argparse.Namespace) -> int:
    from social.providers.errors import AuthenticationError, CapabilityUnsupported

    try:
        start = _manager().start_oauth(args.platform)
    except (AuthenticationError, CapabilityUnsupported) as exc:
        print(f'{{"status": "BLOCKED_EXTERNAL", "provider": "{args.platform}", "reason": "oauth_not_configured"}}')
        print(str(exc))
        return 1
    print(f"provider={start.provider}")
    print(f"authorization_url={start.url}")
    print("请在浏览器打开授权链接。")
    print("登录你的账号。")
    print("完成授权。")
    print("不要把密码或验证码发给我。")
    print("完成后告诉我“授权完成”。")
    if not args.listen:
        return 0
    args.redirect_uri = start.redirect_uri
    return cmd_oauth_callback(args)


def cmd_oauth_callback(args: argparse.Namespace) -> int:
    from social.auth.oauth import listen_for_callback
    from social.providers.errors import AuthenticationError, CapabilityUnsupported

    redirect = getattr(args, "redirect_uri", None) or _provider_redirect(args.platform)
    if not redirect:
        print('{"status": "BLOCKED_EXTERNAL", "reason": "redirect_uri missing"}')
        return 1
    try:
        payload = listen_for_callback(redirect, timeout=int(getattr(args, "timeout", 300) or 300))
        if payload.get("error") or not payload.get("code") or not payload.get("state"):
            print('{"status": "FAIL", "reason": "oauth callback missing code/state"}')
            return 1
        account = _manager().complete_oauth(args.platform, code=payload["code"], state=payload["state"])
    except (AuthenticationError, CapabilityUnsupported, OSError) as exc:
        print('{"status": "BLOCKED_EXTERNAL", "reason": "oauth_callback_blocked"}')
        print(str(exc))
        return 1
    print(f"provider={account.provider} account_id={account.account_id} status={account.status}")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    runtime = _runtime()
    from content.runtime import ContinuityRuntime
    if not args.package_id:
        print(json.dumps({"status": "FAIL", "reason": "package_id is required; do not synthesize a ContentPackage"}))
        return 1
    continuity = ContinuityRuntime.production()
    package = continuity.store.get_package(args.package_id)
    if package is None:
        print(json.dumps({"status": "FAIL", "reason": f"unknown content package: {args.package_id}"}))
        return 1
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
            "publication": False,
        }
        if getattr(package, "account_id", None):
            from content.runtime import ContinuityRuntime
            ContinuityRuntime.production().record_handoff(package=package, handoff=handoff)
            payload["continuity_recorded"] = True
        print("READY_FOR_XHS")
        print("HANDOFF")
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
    from content.models import MemoryWritebackError
    from content.runtime import ContinuityRuntime
    continuity = ContinuityRuntime.production()
    if getattr(package, "account_id", None):
        try:
            continuity.record_publication(package=package, publication=publication)
            payload["continuity_recorded"] = True
        except MemoryWritebackError as exc:
            payload["continuity_recorded"] = False
            payload["code"] = exc.code
            print(json.dumps(payload, default=str))
            return 1
    print(json.dumps(payload))
    return 0



def bootstrap_production() -> dict:
    """Pure preflight. Never write tokens, API keys, credentials, or accounts."""
    import os
    import stat
    from pathlib import Path as _Path
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

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
    checks["lechuang"] = _item("PASS" if _env(("XIAOLEAI_API_KEY",)) else "BLOCKED_EXTERNAL")

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
    from creative.providers.lechuang.credentials import (
        API_KEY_ENV,
        BASE_URL_ENV,
        DEFAULT_BASE_URL,
        SECRET_ACCOUNT,
        SECRET_PROVIDER,
    )
    from social.auth.secrets import production_secret_store, secret_id

    if args.provider not in {"lechuang", "xiaole", "xiaoleai"}:
        print(f"unsupported provider: {args.provider}")
        return 1
    key = os.getenv(API_KEY_ENV, "").strip()
    url = os.getenv(BASE_URL_ENV, "").strip() or DEFAULT_BASE_URL
    if not key:
        print(f'{{"overall": {{"status": "BLOCKED_EXTERNAL"}}, "reason": "{API_KEY_ENV} missing"}}')
        return 1
    store = production_secret_store()
    store.put_json(
        {"api_key": key, "base_url": url, "provider": "xiaole", "service": "lechuang"},
        ref=secret_id(SECRET_PROVIDER, SECRET_ACCOUNT),
    )
    print('{"provider": "xiaole-lechuang", "status": "STORED"}')
    return 0


def cmd_creative_doctor(_args: argparse.Namespace) -> int:
    from scripts.creative_doctor import main
    return main()


def cmd_creative_generate_image(args: argparse.Namespace) -> int:
    from agents.media.runtime import MediaAgent
    from creative.runtime.container import CreativeRuntime

    if not getattr(args, "prompt", None):
        print(json.dumps({"status": "FAIL", "reason": "prompt is required"}, default=str))
        return 1
    creative = CreativeRuntime.create(allow_mock=False)
    generated = MediaAgent(runtime=creative).run({
        "kind": "generate",
        "brief": args.prompt,
        "workflow_id": "creator-lifestyle-v1",
        "model": args.model,
        "image_size": args.image_size,
        "aspect_ratio": args.aspect_ratio,
        "variant_count": 1,
    })
    run = generated.get("run")
    status = getattr(run, "status", None) or ("BLOCKED" if generated.get("blocked") else "FAILED")
    assets = generated.get("assets") or []
    asset = assets[0] if assets else None
    if status == "SUCCEEDED" and asset is not None:
        from scripts.meiti_doctor import record_image_real_e2e
        record_image_real_e2e(
            asset_id=str(getattr(asset, "asset_id", "") or ""),
            qa_decision=str(getattr(asset, "qa_decision", "") or ""),
            sha256=str(getattr(asset, "sha256", "") or ""),
            mime_type=str(getattr(asset, "mime_type", "") or ""),
            path=str(getattr(asset, "path", "") or ""),
            width=getattr(asset, "width", None),
            height=getattr(asset, "height", None),
            size=getattr(asset, "size", None),
            model=str(getattr(asset, "model", "") or args.model or ""),
            request_id=str(getattr(run, "request_id", "") or getattr(asset, "provider_task_id", "") or ""),
        )
    if generated.get("blocked") or status in {"BLOCKED", "FAILED"}:
        print(json.dumps({
            "status": "BLOCKED_EXTERNAL" if generated.get("blocked") or status == "BLOCKED" else "FAIL",
            "reason": generated.get("error") or generated.get("blocked_reason") or status,
            "workflow_id": generated.get("workflow_id"),
            "run_id": getattr(run, "run_id", None),
        }, default=str))
        return 1
    payload = {
        "status": "succeeded" if status == "SUCCEEDED" else status,
        "provider": "xiaole-lechuang",
        "provider_task_id": getattr(asset, "provider_task_id", None),
        "asset_id": getattr(asset, "asset_id", None),
        "path": getattr(asset, "path", None),
        "sha256": getattr(asset, "sha256", None),
        "width": getattr(asset, "width", None),
        "height": getattr(asset, "height", None),
        "mime_type": getattr(asset, "mime_type", None),
        "size": getattr(asset, "size", None),
        "workflow_id": generated.get("workflow_id"),
        "run_id": getattr(run, "run_id", None),
    }
    print(json.dumps(payload, default=str))
    return 0 if status == "SUCCEEDED" else 1


def cmd_creative_generate_video(args: argparse.Namespace) -> int:
    from creative.providers.xai.client import VIDEO_CONTRACT_VERIFIED, VIDEO_MODEL, VIDEO_NOT_VERIFIED
    from creative.runtime.container import CreativeRuntime

    runtime = CreativeRuntime.create(allow_mock=False)
    adapter = runtime.provider_resolver.providers.get("xai")
    capability = adapter.capability_status("text_to_video") if adapter is not None else {
        "status": "NOT_VERIFIED",
        "reason": VIDEO_NOT_VERIFIED,
    }
    print(json.dumps({
        "status": "NOT_VERIFIED",
        "VIDEO_CONTRACT_VERIFIED": bool(VIDEO_CONTRACT_VERIFIED),
        "VIDEO_PRODUCTION_READY": "NOT_VERIFIED",
        "reason": capability.get("reason") or VIDEO_NOT_VERIFIED,
        "provider": "xai",
        "model": VIDEO_MODEL,
        "prompt_required_context": ["CreativeContext", "PlatformStrategy", "ContinuityContext"],
        "source_asset_id": getattr(args, "source_asset_id", None),
        "evidence_checked": [
            "creative/providers/xai/models.yaml",
            "creative/providers/xai/client.py",
            "creative/providers/xai/adapter.py",
            "creative/providers/capabilities/registry.yaml",
        ],
    }))
    return 1


def cmd_creative_image_to_video(args: argparse.Namespace) -> int:
    return cmd_creative_generate_video(args)


def _continuity(*, testing: bool = False):
    from content.runtime import ContinuityRuntime
    if testing:
        return ContinuityRuntime.testing()
    return ContinuityRuntime.production()


def _print_json(payload) -> None:
    print(json.dumps(payload, indent=2, default=str, ensure_ascii=False))


def _account_view(view: dict) -> dict:
    account = view["account"]
    character = view.get("character")
    world = view.get("world")
    series = view.get("series")
    episode = view.get("episode")
    return {
        "platform": account.platform,
        "account_id": account.account_id,
        "display_name": account.display_name,
        "status": account.status,
        "character": None if character is None else {"name": character.name, "character_id": character.character_id, "version": character.version},
        "world": None if world is None else {"name": world.name, "theme": world.core_theme, "world_id": world.world_id},
        "series": None if series is None else {"name": series.name, "series_id": series.series_id, "current_episode_no": series.current_episode_no},
        "latest": None if episode is None else {"episode_no": episode.episode_no, "title": episode.title, "status": episode.content_status},
    }


def cmd_account_list(_args: argparse.Namespace) -> int:
    runtime = _continuity()
    rows = []
    for account in runtime.store.list_accounts():
        rows.append(_account_view(runtime.show_account(account.account_id)))
    if not rows:
        print("no platform accounts")
        return 0
    _print_json(rows)
    return 0


def cmd_account_show(args: argparse.Namespace) -> int:
    runtime = _continuity()
    account_id = args.account_id
    if not account_id:
        account = runtime.store.active_account(platform=args.platform) if args.platform else runtime.store.active_account()
        if account is None:
            print("no active platform account")
            return 1
        account_id = account.account_id
    _print_json(_account_view(runtime.show_account(account_id)))
    return 0


def cmd_account_create(args: argparse.Namespace) -> int:
    from content.models import AccountWorld, VirtualCharacter
    from uuid import uuid4

    runtime = _continuity()
    account = runtime.create_account(platform=args.platform, display_name=args.name)
    if args.character:
        runtime.bind_character(account.account_id, VirtualCharacter(
            character_id=uuid4().hex,
            account_id=account.account_id,
            name=args.character,
            gender=args.gender or "",
            age_range=args.age_range or "",
        ))
    if args.world:
        runtime.bind_world(account.account_id, AccountWorld(
            world_id=uuid4().hex,
            account_id=account.account_id,
            name=args.world,
            world_description=args.world_description or "",
            core_theme=args.theme or "",
            tone=args.tone or "",
        ))
    if args.series:
        runtime.create_series(account_id=account.account_id, name=args.series)
    runtime.store.activate_account(account.account_id)
    _print_json(_account_view(runtime.show_account(account.account_id)))
    return 0


def cmd_account_activate(args: argparse.Namespace) -> int:
    runtime = _continuity()
    account = runtime.store.activate_account(args.account_id)
    _print_json(_account_view(runtime.show_account(account.account_id)))
    return 0


def cmd_account_character(args: argparse.Namespace) -> int:
    from content.models import VirtualCharacter
    from uuid import uuid4

    runtime = _continuity()
    account = runtime.store.get_account(args.account_id) if args.account_id else runtime.store.active_account(platform=args.platform)
    if account is None:
        print("no platform account")
        return 1
    if args.name:
        runtime.bind_character(account.account_id, VirtualCharacter(
            character_id=uuid4().hex,
            account_id=account.account_id,
            name=args.name,
            gender=args.gender or "",
            age_range=args.age_range or "",
        ))
    _print_json(_account_view(runtime.show_account(account.account_id)))
    return 0


def cmd_account_world(args: argparse.Namespace) -> int:
    from content.models import AccountWorld
    from uuid import uuid4

    runtime = _continuity()
    account = runtime.store.get_account(args.account_id) if args.account_id else runtime.store.active_account(platform=args.platform)
    if account is None:
        print("no platform account")
        return 1
    if args.name:
        runtime.bind_world(account.account_id, AccountWorld(
            world_id=uuid4().hex,
            account_id=account.account_id,
            name=args.name,
            world_description=args.description or "",
            core_theme=args.theme or "",
        ))
    _print_json(_account_view(runtime.show_account(account.account_id)))
    return 0


def cmd_account_history(args: argparse.Namespace) -> int:
    runtime = _continuity()
    account = runtime.store.get_account(args.account_id) if args.account_id else runtime.store.active_account(platform=args.platform)
    if account is None:
        print("no platform account")
        return 1
    history = runtime.history(account.account_id)
    _print_json({
        "account": account.label(),
        "series": [{"name": item.name, "episode_no": item.current_episode_no, "series_id": item.series_id} for item in history["series"]],
        "episodes": [{"episode_no": item.episode_no, "title": item.title, "status": item.content_status, "series_id": item.series_id} for item in history["episodes"]],
        "publications": [item.value for item in history["memories"] if item.key == "published"],
        "lineage": [{"asset_id": item.asset_id, "episode_id": item.episode_id, "attempt_no": item.attempt_no, "provider_task_id": item.provider_task_id} for item in history["lineage"]],
    })
    return 0


def cmd_content_calendar(_args: argparse.Namespace) -> int:
    runtime = _continuity()
    rows = runtime.calendar(account_id=getattr(_args, "account_id", None))
    if not rows:
        print("no content calendar rows")
        return 0
    _print_json(rows)
    return 0


def cmd_content_tomorrow(args: argparse.Namespace) -> int:
    runtime = _continuity()
    account = runtime.store.get_account(args.account_id) if args.account_id else runtime.store.active_account(platform=args.platform)
    if account is None:
        print("no platform account")
        return 1
    _print_json(runtime.tomorrow(account_id=account.account_id))
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    runtime = _continuity()
    _print_json(runtime.dashboard(account_id=args.account_id, platform=args.platform))
    return 0


def cmd_task_next(args: argparse.Namespace) -> int:
    runtime = _continuity()
    task = runtime.get_next_action(account_id=args.account_id, platform=args.platform)
    if task is None:
        print("no next action")
        return 0
    _print_json({
        "task_id": task.task_id,
        "task_type": task.task_type,
        "status": task.status,
        "title": task.title,
        "account_id": task.account_id,
        "platform": task.platform,
        "episode_id": task.episode_id,
        "next_task_type": task.next_task_type,
        "due_at": task.due_at,
    })
    return 0


def cmd_task_today(args: argparse.Namespace) -> int:
    runtime = _continuity()
    rows = runtime.get_today_tasks(account_id=args.account_id, platform=args.platform)
    _print_json([
        {
            "task_id": item.task_id,
            "task_type": item.task_type,
            "status": item.status,
            "title": item.title,
            "due_at": item.due_at,
            "episode_id": item.episode_id,
        }
        for item in rows
    ])
    return 0


def cmd_task_blocked(args: argparse.Namespace) -> int:
    runtime = _continuity()
    rows = runtime.get_blocked_tasks(account_id=args.account_id, platform=args.platform)
    _print_json([
        {
            "task_id": item.task_id,
            "task_type": item.task_type,
            "status": item.status,
            "blocked_reason": item.blocked_reason,
            "account_id": item.account_id,
        }
        for item in rows
    ])
    return 0


def cmd_production_readiness(args: argparse.Namespace) -> int:
    runtime = _continuity()
    payload = runtime.production_readiness(account_id=args.account_id)
    _print_json(payload)
    return 0 if payload.get("CORE_PRODUCTION") == "READY" else 1


def cmd_account_override(args: argparse.Namespace) -> int:
    runtime = _continuity()
    account = runtime.store.get_account(args.account_id) if args.account_id else runtime.store.active_account(platform=args.platform)
    if account is None:
        print("no platform account")
        return 1
    profile = runtime.override_profile(
        account.account_id,
        field_name=args.field,
        value=args.value,
        reason=args.reason,
        changed_by=args.changed_by,
    )
    _print_json({
        "account_id": profile.account_id,
        "field": args.field,
        "value": profile.field_value(args.field),
        "source": "USER_OVERRIDE",
        "reason": args.reason,
    })
    return 0


def cmd_creative_continue(args: argparse.Namespace) -> int:
    from content.models import AssetFreshnessError, IsolationError
    from creative.errors import SchemaNotReady

    text = " ".join(getattr(args, "text", None) or ()) or getattr(args, "prompt", None) or "继续昨天"
    try:
        runtime = _continuity()
        if getattr(args, "account_id", None):
            prepared_list = [runtime.prepare(text, platform=getattr(args, "platform", None), account_id=args.account_id)]
        elif getattr(args, "platform", None):
            prepared_list = [runtime.prepare(text, platform=args.platform)]
        else:
            prepared_list = runtime.packages_for_request(text)
    except SchemaNotReady as exc:
        print(json.dumps({"status": "NOT_CONFIGURED", "reason": str(exc)}, default=str))
        return 1
    except IsolationError as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, default=str))
        return 1
    results = []
    overall = 0
    for prepared in prepared_list:
        context = prepared["context"]
        episode = prepared.get("episode")
        try:
            prompt = runtime.compile_prompt(
                account_id=context.account_id,
                platform=context.platform,
                request=text,
                kind=getattr(args, "kind", None),
                episode=episode,
                intent=str((prepared["target"].extras or {}).get("intent") or "CONTINUE"),
                source_asset_id=getattr(args, "source_asset_id", None),
            )
        except AssetFreshnessError as exc:
            overall = 1
            results.append({
                "status": "FAIL",
                "code": getattr(exc, "code", "") or "DUPLICATE_CONTENT",
                "reason": str(exc),
                "account_id": context.account_id,
                "episode_id": context.episode_id,
            })
            continue
        results.append({
            "status": "COPY_READY",
            "prompt_id": prompt.prompt_id,
            "kind": prompt.kind,
            "platform": prompt.platform,
            "account_id": prompt.account_id,
            "series_id": prompt.series_id,
            "episode_id": prompt.episode_id,
            "episode_no": episode.episode_no if episode else None,
            "character_id": prompt.character_id,
            "world_id": prompt.world_id,
            "copy_ready": prompt.copy_ready,
            "recommended_model": prompt.recommended_model,
            "isolation": prepared["isolation"],
            "character_qa": prepared["character_qa"],
            "execution": "manual-lechuang",
        })
    _print_json(results[0] if len(results) == 1 else results)
    return overall


def cmd_creative_compile_prompt(args: argparse.Namespace) -> int:
    from content.models import AssetFreshnessError, IsolationError

    runtime = _continuity()
    text = " ".join(getattr(args, "text", None) or ()) or getattr(args, "prompt", None) or ""
    if not text:
        print(json.dumps({"status": "FAIL", "reason": "prompt is required"}, default=str))
        return 1
    try:
        prepared = runtime.prepare(text, platform=args.platform, account_id=args.account_id)
        prompt = runtime.compile_prompt(
            account_id=prepared["account"].account_id,
            platform=prepared["account"].platform,
            request=text,
            kind=args.kind,
            episode=prepared.get("episode"),
            source_asset_id=args.source_asset_id,
        )
    except IsolationError as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, default=str))
        return 1
    except AssetFreshnessError as exc:
        print(json.dumps({"status": "FAIL", "code": exc.code, "reason": str(exc)}, default=str))
        return 1
    _print_json({
        "status": "COPY_READY",
        "prompt_id": prompt.prompt_id,
        "kind": prompt.kind,
        "copy_ready": prompt.copy_ready,
        "account_id": prompt.account_id,
        "platform": prompt.platform,
        "episode_id": prompt.episode_id,
        "execution": "manual-lechuang",
    })
    return 0


def cmd_creative_import_asset(args: argparse.Namespace) -> int:
    from content.models import AssetFreshnessError, ConfigurationBlocked, CrossPlatformAssetReuse, ExistingAssetError, IsolationError

    runtime = _continuity()
    try:
        imported = runtime.import_asset(
            args.path,
            account_id=args.account_id,
            platform=args.platform,
            episode_id=args.episode_id,
            asset_role=args.role,
            reuse_mode=args.reuse_mode,
            intent=args.intent,
            parent_asset_id=args.parent_asset_id,
            source_asset_id=args.source_asset_id,
            prompt_id=args.prompt_id,
            model=args.model,
            tool=args.tool,
            no_prompt_reference=bool(getattr(args, "no_prompt_reference", False)),
        )
    except FileNotFoundError as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, default=str))
        return 1
    except IsolationError as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, default=str))
        return 1
    except ConfigurationBlocked as exc:
        print(json.dumps({"status": "FAIL", "code": exc.code, "reason": str(exc)}, default=str))
        return 1
    except ExistingAssetError as exc:
        print(json.dumps({"status": "FAIL", "code": exc.code, "reason": str(exc)}, default=str))
        return 1
    except AssetFreshnessError as exc:
        print(json.dumps({"status": "FAIL", "code": exc.code, "reason": str(exc)}, default=str))
        return 1
    except CrossPlatformAssetReuse as exc:
        print(json.dumps({"status": "FAIL", "code": "CROSS_PLATFORM_ASSET_REUSE", "reason": str(exc)}, default=str))
        return 1
    asset = imported["asset"]
    lineage = imported["lineage"]
    _print_json({
        "status": imported["status"],
        "asset_id": asset.asset_id,
        "sha256": asset.sha256,
        "asset_role": asset.asset_role,
        "lifecycle": asset.lifecycle,
        "platform": asset.platform,
        "account_id": asset.account_id,
        "episode_id": asset.episode_id,
        "pool_id": asset.pool_id,
        "parent_asset_id": asset.parent_asset_id,
        "lineage_id": lineage.lineage_id,
        "reuse_mode": lineage.reuse_mode,
        "qa": imported["qa"],
        "generation_mode": "MANUAL_CREATIVE_TOOL",
    })
    return 0 if (imported.get("qa") or {}).get("decision") == "pass" else 1


def cmd_creative_series(args: argparse.Namespace) -> int:
    runtime = _continuity()
    account = runtime.store.get_account(args.account_id) if args.account_id else runtime.store.active_account(platform=args.platform)
    if account is None:
        print("no platform account")
        return 1
    if args.name:
        series = runtime.create_series(account_id=account.account_id, name=args.name, description=args.description or "")
        _print_json({"series_id": series.series_id, "name": series.name, "account_id": series.account_id})
        return 0
    _print_json([{"name": item.name, "series_id": item.series_id, "current_episode_no": item.current_episode_no, "status": item.status} for item in runtime.store.list_series(account.account_id)])
    return 0


def cmd_creative_account(args: argparse.Namespace) -> int:
    return cmd_account_show(args)


def cmd_creative_character(args: argparse.Namespace) -> int:
    return cmd_account_character(args)


def cmd_creative_world(args: argparse.Namespace) -> int:
    return cmd_account_world(args)


def cmd_creative_episode(args: argparse.Namespace) -> int:
    runtime = _continuity()
    account = runtime.store.active_account(platform=args.platform) if args.platform else runtime.store.active_account()
    if account is None:
        print("no platform account")
        return 1
    history = runtime.history(account.account_id)
    _print_json([{"episode_no": item.episode_no, "title": item.title, "status": item.content_status, "episode_id": item.episode_id} for item in history["episodes"]])
    return 0


def cmd_creative_history(args: argparse.Namespace) -> int:
    return cmd_account_history(args)


def cmd_creative_inspect(args: argparse.Namespace) -> int:
    runtime = _continuity()
    text = " ".join(getattr(args, "text", None) or ()) or "inspect"
    prepared = runtime.prepare(text, platform=args.platform, account_id=args.account_id)
    context = prepared["context"]
    _print_json({
        "resolved_target": context.resolved_target,
        "character": context.character_context,
        "world": context.world_context,
        "continuity": context.continuity_context,
        "platform": context.platform_context,
        "prompt": context.normalized_prompt,
        "isolation": prepared["isolation"],
        "character_qa": prepared["character_qa"],
    })
    return 0


def cmd_package_from_episode(args: argparse.Namespace) -> int:
    from content.models import CreativeContext
    from uuid import uuid4

    runtime = _continuity()
    account = runtime.store.get_account(args.account_id)
    if account is None:
        print(json.dumps({"status": "FAIL", "reason": "unknown platform account"}))
        return 1
    episode = runtime.store.get_episode(args.episode_id, account_id=args.account_id)
    if episode is None:
        print(json.dumps({"status": "FAIL", "reason": "episode not found"}))
        return 1
    asset = runtime.store.get_media_asset(episode.primary_asset_id) if episode.primary_asset_id else None
    if asset is None:
        print(json.dumps({"status": "FAIL", "reason": "episode has no primary asset"}))
        return 1
    context = CreativeContext(
        context_id=uuid4().hex,
        account_id=account.account_id,
        platform=account.platform,
        character_id=account.character_id,
        world_id=account.world_id,
        series_id=episode.series_id,
        episode_id=episode.episode_id,
        user_request=episode.brief,
        creative_request=episode.title,
        normalized_prompt=episode.brief,
    )
    package = runtime.package_from_generation(
        context=context,
        assets=[asset],
        title=args.title or episode.title,
        body=args.body or episode.brief,
        prompt_id=episode.prompt_id,
        status="PACKAGE_READY",
    )
    _print_json({
        "status": "PACKAGE_READY",
        "package_id": package.package_id,
        "episode_id": package.episode_id,
        "primary_assets": list(package.primary_assets),
        "prompt_id": package.prompt_id,
    })
    return 0


def cmd_handoff(args: argparse.Namespace) -> int:
    return cmd_publish(args)


def cmd_analytics_record(args: argparse.Namespace) -> int:
    from content.models import AnalyticsRecord
    from uuid import uuid4

    runtime = _continuity()
    record = runtime.record_analytics(AnalyticsRecord(
        analytics_id=uuid4().hex,
        account_id=args.account_id,
        platform=args.platform,
        episode_id=args.episode_id,
        package_id=args.package_id,
        handoff_id=args.handoff_id,
        publication_id=args.publication_id,
        impressions=args.impressions,
        likes=args.likes,
        favorites=args.favorites,
        comments=args.comments,
        shares=args.shares,
        clicks=args.clicks,
        followers_gained=args.followers,
        followers_delta=args.followers_delta,
        published_at=args.published_at,
        observed_at=args.observed_at,
        topic=args.topic or "",
        cover=args.cover or "",
        prompt_pattern=args.prompt_pattern or "",
        source="manual",
    ))
    _print_json({"status": "ANALYTICS_IMPORTED", "analytics_id": record.analytics_id, "episode_id": record.episode_id})
    return 0


def cmd_learning_record(args: argparse.Namespace) -> int:
    from content.models import LearningRecord, MemoryWritebackError
    from uuid import uuid4

    runtime = _continuity()
    try:
        record = runtime.record_learning(LearningRecord(
            learning_id=uuid4().hex,
            account_id=args.account_id,
            platform=args.platform,
            episode_id=args.episode_id,
            analytics_id=args.analytics_id,
            prompt_id=getattr(args, "prompt_id", None),
            asset_id=getattr(args, "asset_id", None),
            what_worked=args.what_worked or "",
            what_failed=args.what_failed or "",
            visual_learning=args.visual_learning or "",
            content_learning=args.content_learning or "",
            prompt_learning=args.prompt_learning or "",
            audience_learning=args.audience_learning or "",
            next_recommendation=args.next_recommendation or "",
            reason=args.reason or "",
            source_episode_ids=tuple(item for item in (args.episode_id,) if item),
        ))
    except MemoryWritebackError as exc:
        print(json.dumps({"status": "FAIL", "code": exc.code, "reason": str(exc)}))
        return 1
    _print_json({"status": "LEARNING_WRITTEN", "learning_id": record.learning_id, "reason": record.reason})
    return 0


def cmd_production_show(args: argparse.Namespace) -> int:
    runtime = _continuity()
    account = runtime.store.get_account(args.account_id) if args.account_id else runtime.store.active_account(platform=args.platform)
    if account is None:
        print("no platform account")
        return 1
    evidence = runtime.store.list_evidence(account_id=account.account_id, episode_id=args.episode_id)
    learning = runtime.store.list_learning(account_id=account.account_id, platform=account.platform)
    _print_json({
        "account_id": account.account_id,
        "platform": account.platform,
        "evidence": [{"kind": item.kind, "status": item.status, "episode_id": item.episode_id, "asset_id": item.asset_id} for item in evidence],
        "learning": [{"learning_id": item.learning_id, "reason": item.reason, "next_recommendation": item.next_recommendation} for item in learning],
        "real_day_1": any(item.kind == "DAY_001_REAL_ASSET_IMPORTED" for item in evidence),
        "real_day_2": any(item.kind == "DAY_002_REAL_ASSET_IMPORTED" for item in evidence),
        "real_day_3": any(item.kind == "DAY_003_REAL_ASSET_IMPORTED" for item in evidence),
    })
    return 0


def cmd_sandbox_seed(_args: argparse.Namespace) -> int:
    runtime = _continuity()
    seeded = runtime.seed_sandbox()
    _print_json({
        "xiaohongshu": _account_view(seeded["xiaohongshu"]),
        "douyin": _account_view(seeded["douyin"]),
        "shared_character": False,
        "shared_world": False,
        "shared_pool": False,
    })
    return 0


def cmd_creative_lineage(args: argparse.Namespace) -> int:
    runtime = _continuity()
    account = runtime.store.get_account(args.account_id) if args.account_id else runtime.store.active_account(platform=args.platform)
    if account is None:
        print("no platform account")
        return 1
    rows = runtime.store.list_lineage(account_id=account.account_id)
    _print_json([{
        "asset_id": item.asset_id,
        "account_id": item.account_id,
        "series_id": item.series_id,
        "episode_id": item.episode_id,
        "content_package_id": item.content_package_id,
        "creative_context_id": item.creative_context_id,
        "provider": item.provider,
        "provider_task_id": item.provider_task_id,
        "model": item.model,
        "attempt_no": item.attempt_no,
        "qa_decision": item.qa_decision,
        "published": item.published,
        "user_request": item.user_request,
    } for item in rows])
    return 0


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(prog="meiti")
    sub = parser.add_subparsers(dest="group", required=True)
    boot = sub.add_parser("bootstrap-production")
    boot.set_defaults(func=cmd_bootstrap_production)
    cred = sub.add_parser("credentials")
    cred_sub = cred.add_subparsers(dest="command", required=True)
    put = cred_sub.add_parser("put")
    put.add_argument("--provider", required=True, choices=("lechuang", "xiaole", "xiaoleai"))
    put.set_defaults(func=cmd_credentials_put)
    creative = sub.add_parser("creative")
    creative_sub = creative.add_subparsers(dest="command", required=True)
    creative_sub.add_parser("doctor").set_defaults(func=cmd_creative_doctor)
    gen_image = creative_sub.add_parser("generate-image")
    gen_image.add_argument("--prompt", required=True)
    gen_image.add_argument("--model", default="gpt-image-2")
    gen_image.add_argument("--image-size", default="2K")
    gen_image.add_argument("--aspect-ratio", default="9:16")
    gen_image.set_defaults(func=cmd_creative_generate_image)
    gen_video = creative_sub.add_parser("generate-video")
    gen_video.add_argument("--prompt", default="")
    gen_video.set_defaults(func=cmd_creative_generate_video)
    i2v = creative_sub.add_parser("image-to-video")
    i2v.add_argument("--prompt", default="")
    i2v.set_defaults(func=cmd_creative_image_to_video)
    cont = creative_sub.add_parser("continue")
    cont.add_argument("text", nargs="*")
    cont.add_argument("--platform")
    cont.add_argument("--account-id")
    cont.add_argument("--prompt")
    cont.add_argument("--model", default="gpt-image-2")
    cont.add_argument("--image-size", default="2K")
    cont.add_argument("--aspect-ratio", default="9:16")
    cont.add_argument("--kind", choices=("IMAGE", "VIDEO", "IMAGE_TO_VIDEO"))
    cont.add_argument("--source-asset-id")
    cont.set_defaults(func=cmd_creative_continue)
    compile_prompt = creative_sub.add_parser("compile-prompt")
    compile_prompt.add_argument("text", nargs="*")
    compile_prompt.add_argument("--platform")
    compile_prompt.add_argument("--account-id")
    compile_prompt.add_argument("--prompt")
    compile_prompt.add_argument("--kind", choices=("IMAGE", "VIDEO", "IMAGE_TO_VIDEO"))
    compile_prompt.add_argument("--source-asset-id")
    compile_prompt.set_defaults(func=cmd_creative_compile_prompt)
    import_asset = creative_sub.add_parser("import-asset")
    import_asset.add_argument("--path", required=True)
    import_asset.add_argument("--account-id", required=True)
    import_asset.add_argument("--platform", required=True)
    import_asset.add_argument("--episode-id", required=True)
    import_asset.add_argument("--role", default="GENERATED_PRIMARY")
    import_asset.add_argument("--reuse-mode", default="NONE")
    import_asset.add_argument("--intent", default="GENERATE")
    import_asset.add_argument("--parent-asset-id")
    import_asset.add_argument("--source-asset-id")
    import_asset.add_argument("--prompt-id")
    import_asset.add_argument("--no-prompt-reference", action="store_true")
    import_asset.add_argument("--model", default="UNKNOWN")
    import_asset.add_argument("--tool", default="lechuang")
    import_asset.set_defaults(func=cmd_creative_import_asset)
    series = creative_sub.add_parser("series")
    series.add_argument("--platform")
    series.add_argument("--account-id")
    series.add_argument("--name")
    series.add_argument("--description")
    series.set_defaults(func=cmd_creative_series)
    creative_account = creative_sub.add_parser("account")
    creative_account.add_argument("--platform")
    creative_account.add_argument("--account-id")
    creative_account.set_defaults(func=cmd_creative_account)
    creative_character = creative_sub.add_parser("character")
    creative_character.add_argument("--platform")
    creative_character.add_argument("--account-id")
    creative_character.add_argument("--name")
    creative_character.add_argument("--gender")
    creative_character.add_argument("--age-range")
    creative_character.set_defaults(func=cmd_creative_character)
    creative_world = creative_sub.add_parser("world")
    creative_world.add_argument("--platform")
    creative_world.add_argument("--account-id")
    creative_world.add_argument("--name")
    creative_world.add_argument("--description")
    creative_world.add_argument("--theme")
    creative_world.set_defaults(func=cmd_creative_world)
    creative_episode = creative_sub.add_parser("episode")
    creative_episode.add_argument("--platform")
    creative_episode.set_defaults(func=cmd_creative_episode)
    creative_history = creative_sub.add_parser("history")
    creative_history.add_argument("--platform")
    creative_history.add_argument("--account-id")
    creative_history.set_defaults(func=cmd_creative_history)
    inspect_cmd = creative_sub.add_parser("inspect")
    inspect_cmd.add_argument("text", nargs="*")
    inspect_cmd.add_argument("--platform")
    inspect_cmd.add_argument("--account-id")
    inspect_cmd.set_defaults(func=cmd_creative_inspect)
    lineage = creative_sub.add_parser("lineage")
    lineage.add_argument("--platform")
    lineage.add_argument("--account-id")
    lineage.set_defaults(func=cmd_creative_lineage)
    account = sub.add_parser("account")
    account_sub = account.add_subparsers(dest="command", required=True)
    account_sub.add_parser("list").set_defaults(func=cmd_account_list)
    show = account_sub.add_parser("show")
    show.add_argument("--account-id")
    show.add_argument("--platform")
    show.set_defaults(func=cmd_account_show)
    create = account_sub.add_parser("create")
    create.add_argument("--platform", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--character")
    create.add_argument("--gender")
    create.add_argument("--age-range")
    create.add_argument("--world")
    create.add_argument("--world-description")
    create.add_argument("--theme")
    create.add_argument("--tone")
    create.add_argument("--series")
    create.set_defaults(func=cmd_account_create)
    activate = account_sub.add_parser("activate")
    activate.add_argument("account_id")
    activate.set_defaults(func=cmd_account_activate)
    account_character = account_sub.add_parser("character")
    account_character.add_argument("--account-id")
    account_character.add_argument("--platform")
    account_character.add_argument("--name")
    account_character.add_argument("--gender")
    account_character.add_argument("--age-range")
    account_character.set_defaults(func=cmd_account_character)
    account_world = account_sub.add_parser("world")
    account_world.add_argument("--account-id")
    account_world.add_argument("--platform")
    account_world.add_argument("--name")
    account_world.add_argument("--description")
    account_world.add_argument("--theme")
    account_world.set_defaults(func=cmd_account_world)
    account_history = account_sub.add_parser("history")
    account_history.add_argument("--account-id")
    account_history.add_argument("--platform")
    account_history.set_defaults(func=cmd_account_history)
    account_override = account_sub.add_parser("override")
    account_override.add_argument("--account-id")
    account_override.add_argument("--platform")
    account_override.add_argument("--field", required=True)
    account_override.add_argument("--value", required=True)
    account_override.add_argument("--reason", required=True)
    account_override.add_argument("--changed-by", default="operator")
    account_override.set_defaults(func=cmd_account_override)
    content = sub.add_parser("content")
    content_sub = content.add_subparsers(dest="command", required=True)
    calendar_cmd = content_sub.add_parser("calendar")
    calendar_cmd.add_argument("--account-id")
    calendar_cmd.set_defaults(func=cmd_content_calendar)
    tomorrow_cmd = content_sub.add_parser("tomorrow")
    tomorrow_cmd.add_argument("--account-id")
    tomorrow_cmd.add_argument("--platform")
    tomorrow_cmd.set_defaults(func=cmd_content_tomorrow)
    package_cmd = content_sub.add_parser("package")
    package_cmd.add_argument("--account-id", required=True)
    package_cmd.add_argument("--episode-id", required=True)
    package_cmd.add_argument("--platform")
    package_cmd.add_argument("--title")
    package_cmd.add_argument("--body")
    package_cmd.set_defaults(func=cmd_package_from_episode)
    social = sub.add_parser("social")
    social_sub = social.add_subparsers(dest="command", required=True)
    social_sub.add_parser("accounts").set_defaults(func=cmd_accounts)
    connect = social_sub.add_parser("connect")
    connect.add_argument("platform")
    connect.add_argument("--code")
    connect.add_argument("--state")
    connect.add_argument("--username")
    connect.add_argument("--account-id")
    connect.set_defaults(func=cmd_connect)
    oauth_start = social_sub.add_parser("oauth-start")
    oauth_start.add_argument("platform")
    oauth_start.add_argument("--listen", action="store_true")
    oauth_start.add_argument("--timeout", type=int, default=300)
    oauth_start.set_defaults(func=cmd_oauth_start)
    oauth_cb = social_sub.add_parser("oauth-callback")
    oauth_cb.add_argument("platform")
    oauth_cb.add_argument("--timeout", type=int, default=300)
    oauth_cb.set_defaults(func=cmd_oauth_callback)
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
    publish.add_argument("--package-id", required=True)
    publish.add_argument("--job-id")
    publish.add_argument("--account-id")
    publish.add_argument("--media", nargs="*")
    publish.add_argument("--commerce-intent", default="none")
    publish.add_argument("--price")
    publish.add_argument("--category-id")
    publish.set_defaults(func=cmd_publish)
    handoff = social_sub.add_parser("handoff")
    handoff.add_argument("--platform", default="xiaohongshu")
    handoff.add_argument("--package-id", required=True)
    handoff.add_argument("--account-id")
    handoff.add_argument("--job-id")
    handoff.add_argument("--title", default="")
    handoff.add_argument("--body", default="")
    handoff.set_defaults(func=cmd_handoff)
    social_sub.add_parser("doctor").set_defaults(func=cmd_doctor)
    analytics = sub.add_parser("analytics")
    analytics_sub = analytics.add_subparsers(dest="command", required=True)
    analytics_record = analytics_sub.add_parser("record")
    analytics_record.add_argument("--account-id", required=True)
    analytics_record.add_argument("--platform", required=True)
    analytics_record.add_argument("--episode-id")
    analytics_record.add_argument("--package-id")
    analytics_record.add_argument("--handoff-id")
    analytics_record.add_argument("--publication-id")
    analytics_record.add_argument("--impressions", type=int)
    analytics_record.add_argument("--likes", type=int)
    analytics_record.add_argument("--favorites", type=int)
    analytics_record.add_argument("--comments", type=int)
    analytics_record.add_argument("--shares", type=int)
    analytics_record.add_argument("--clicks", type=int)
    analytics_record.add_argument("--followers", type=int)
    analytics_record.add_argument("--followers-delta", type=int)
    analytics_record.add_argument("--published-at")
    analytics_record.add_argument("--observed-at")
    analytics_record.add_argument("--topic")
    analytics_record.add_argument("--cover")
    analytics_record.add_argument("--prompt-pattern")
    analytics_record.set_defaults(func=cmd_analytics_record)
    learning = sub.add_parser("learning")
    learning_sub = learning.add_subparsers(dest="command", required=True)
    learning_record = learning_sub.add_parser("record")
    learning_record.add_argument("--account-id", required=True)
    learning_record.add_argument("--platform", required=True)
    learning_record.add_argument("--episode-id")
    learning_record.add_argument("--analytics-id")
    learning_record.add_argument("--prompt-id")
    learning_record.add_argument("--asset-id")
    learning_record.add_argument("--what-worked")
    learning_record.add_argument("--what-failed")
    learning_record.add_argument("--visual-learning")
    learning_record.add_argument("--content-learning")
    learning_record.add_argument("--prompt-learning")
    learning_record.add_argument("--audience-learning")
    learning_record.add_argument("--next-recommendation")
    learning_record.add_argument("--reason")
    learning_record.set_defaults(func=cmd_learning_record)
    production = sub.add_parser("production")
    production_sub = production.add_subparsers(dest="command", required=True)
    production_sub.add_parser("seed").set_defaults(func=cmd_sandbox_seed)
    production_show = production_sub.add_parser("show")
    production_show.add_argument("--account-id")
    production_show.add_argument("--platform")
    production_show.add_argument("--episode-id")
    production_show.set_defaults(func=cmd_production_show)
    production_ready = production_sub.add_parser("readiness")
    production_ready.add_argument("--account-id")
    production_ready.set_defaults(func=cmd_production_readiness)
    dash = sub.add_parser("dashboard")
    dash.add_argument("--account-id")
    dash.add_argument("--platform")
    dash.set_defaults(func=cmd_dashboard)
    task = sub.add_parser("task")
    task_sub = task.add_subparsers(dest="command", required=True)
    task_next = task_sub.add_parser("next")
    task_next.add_argument("--account-id")
    task_next.add_argument("--platform")
    task_next.set_defaults(func=cmd_task_next)
    task_today = task_sub.add_parser("today")
    task_today.add_argument("--account-id")
    task_today.add_argument("--platform")
    task_today.set_defaults(func=cmd_task_today)
    task_blocked = task_sub.add_parser("blocked")
    task_blocked.add_argument("--account-id")
    task_blocked.add_argument("--platform")
    task_blocked.set_defaults(func=cmd_task_blocked)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
