#!/usr/bin/env python3
"""Smoke the human production chain without forging Lechuang or publish evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def run() -> dict:
    from content.runtime import ContinuityRuntime

    runtime = ContinuityRuntime.testing()
    seeded = runtime.seed_sandbox()
    account = seeded["xiaohongshu"]["account"]
    series = runtime.store.active_series(account.account_id)
    episode = runtime.continue_series(
        account_id=account.account_id,
        series_id=series.series_id,
        title="健身日常",
        brief="今天帮我做一条小红书健身日常。",
    )
    prompt = runtime.compile_prompt(
        account_id=account.account_id,
        platform="xiaohongshu",
        request="今天帮我做一条小红书健身日常。",
        kind="IMAGE",
        episode=episode,
    )
    next_action = runtime.get_next_action(account_id=account.account_id)
    readiness = runtime.production_readiness(account_id=account.account_id, persist=False)
    dashboard = runtime.dashboard(account_id=account.account_id)
    return {
        "account_id": account.account_id,
        "platform": account.platform,
        "episode_id": episode.episode_id,
        "prompt_id": prompt.prompt_id,
        "copy_ready": bool(prompt.copy_ready),
        "next_action": None if next_action is None else {
            "task_type": next_action.task_type,
            "status": next_action.status,
        },
        "dashboard": dashboard.get("next_recommended_action"),
        "SYSTEM_CAPABILITY": readiness.get("SYSTEM_CAPABILITY"),
        "ACCOUNT_CONFIGURATION": readiness.get("ACCOUNT_CONFIGURATION"),
        "CORE_PRODUCTION": readiness.get("CORE_PRODUCTION"),
        "POST_PRODUCTION": readiness.get("POST_PRODUCTION"),
        "PRODUCTION_EVIDENCE": readiness.get("PRODUCTION_EVIDENCE"),
        "ANALYTICS": readiness.get("ANALYTICS"),
        "LEARNING": readiness.get("LEARNING"),
        "FULL_LOOP": readiness.get("FULL_LOOP"),
        "REAL_E2E": "NOT_VERIFIED",
        "note": "Smoke stops at COPY READY. Operator Lechuang import is required for REAL_DAY evidence.",
    }


def main() -> int:
    payload = run()
    print("MEITI_SMOKE_PRODUCTION")
    print(json.dumps(payload, indent=2, default=str, ensure_ascii=False))
    if not payload.get("copy_ready"):
        return 1
    if (payload.get("next_action") or {}).get("task_type") != "CREATIVE_EXECUTION":
        return 1
    if payload.get("CORE_PRODUCTION") != "READY":
        return 1
    if payload.get("PRODUCTION_EVIDENCE") not in {None, "NOT_VERIFIED"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
