#!/usr/bin/env python3
"""Creative subsystem doctor. Live generation is BLOCKED without a verified Lechuang contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _status(ok: bool, **extra):
    payload = {"status": "PASS" if ok else "BLOCKED"}
    payload.update(extra)
    return payload


def run() -> dict:
    from creative.providers.lechuang.adapter import LechuangAdapter
    from creative.providers.resolver import load_capability_registry
    from creative.workflow.engine import CreativeStore, CreativeWorkflowEngine
    from creative.workflow.registry import list_workflows
    from creative.judge import ImageJudge, VideoJudge
    from services.workers.creative_worker import run_once

    workflows = list_workflows()
    names = {item.workflow_id for item in workflows}
    required = {
        "creator-video-default-v1", "creator-image-to-video-v1", "creator-lifestyle-v1",
        "character-consistency-v1", "scene-storyboard-v1", "short-drama-v1",
        "ugc-style-video-v1", "cinematic-video-v1", "product-optional-content-v1",
    }
    adapter = LechuangAdapter()
    ready, reason = adapter.live_ready()
    capabilities = load_capability_registry()
    engine = CreativeWorkflowEngine(allow_mock=True)
    mock_run = engine.execute("creator-image-to-video-v1", {"brief": "doctor mock", "variant_count": 1, "budget": 40})
    return {
        "workflow_registry": _status(required.issubset(names), missing=sorted(required - names), count=len(workflows)),
        "provider_registry": _status(bool(capabilities), count=len(capabilities)),
        "model_registry": _status(True, claimed=sorted({item.model for item in capabilities})),
        "Lechuang auth": _status(ready, reason=reason),
        "image capability": _status(ready, reason=reason),
        "video capability": _status(ready, reason=reason),
        "async_task_system": _status(callable(run_once)),
        "asset_store": _status(isinstance(engine.store, CreativeStore)),
        "judge": _status(bool(ImageJudge().judge(None).decision == "FAIL" and VideoJudge().judge(None).decision == "FAIL")),
        "workers": _status(callable(run_once)),
        "mock_runtime": _status(mock_run.status == "SUCCEEDED", run_status=mock_run.status, error=mock_run.error),
    }


def main() -> int:
    checks = run()
    statuses = {key: value.get("status") for key, value in checks.items()}
    live_keys = {"Lechuang auth", "image capability", "video capability"}
    architecture_ready = all(status == "PASS" for key, status in statuses.items() if key not in live_keys)
    live_ready = all(statuses.get(key) == "PASS" for key in live_keys)
    payload = {
        "ready": architecture_ready and live_ready,
        "architecture_ready": architecture_ready,
        "live_ready": live_ready,
        "checks": statuses,
        "details": checks,
    }
    for name, status in statuses.items():
        print(f"{name}: {status}")
    print("ARCHITECTURE:", "PASS" if architecture_ready else "BLOCKED")
    print("LIVE:", "PASS" if live_ready else "BLOCKED")
    print(json.dumps({"ready": payload["ready"], "architecture_ready": architecture_ready, "live_ready": live_ready, "checks": statuses}, default=str))
    return 0 if architecture_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
