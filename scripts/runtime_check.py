#!/usr/bin/env python3
"""Machine-readable runtime check for Meiti V4.1."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.meiti_doctor import as_payload, run


LIVE_KEYS = {
    "Postiz",
    "Postiz authentication",
    "Postiz integrations",
    "Postiz capabilities",
    "Research",
    "Lechuang",
    "Lechuang authentication",
    "Lechuang capabilities",
}


def main() -> int:
    payload = as_payload(run())
    statuses = payload["checks"]
    architecture_ready = all(status == "PASS" for key, status in statuses.items() if key not in LIVE_KEYS)
    live_ready = all(statuses.get(key) == "PASS" for key in LIVE_KEYS)
    out = {
        "ready": architecture_ready and live_ready,
        "architecture_ready": architecture_ready,
        "live_ready": live_ready,
        "checks": statuses,
    }
    print(json.dumps(out, default=str))
    return 0 if architecture_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
