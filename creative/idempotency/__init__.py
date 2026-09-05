"""Idempotency keys for runs and provider tasks."""

from __future__ import annotations

import hashlib
import json
from typing import Any


class IdempotencyKey:
    @staticmethod
    def run(workflow_id: str, version: str, inputs: dict[str, Any]) -> str:
        payload = json.dumps({"workflow_id": workflow_id, "version": version, "inputs": inputs}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def provider(run_id: str, node_id: str, attempt: int | str) -> str:
        return f"{run_id}:{node_id}:{attempt}"

    @staticmethod
    def creative_job(
        creator_account_id: str,
        episode_id: str,
        prompt_id: str,
        generation_spec: dict[str, Any] | None = None,
    ) -> str:
        payload = json.dumps(
            {
                "creator_account_id": creator_account_id,
                "episode_id": episode_id,
                "prompt_id": prompt_id,
                "generation_spec": generation_spec or {},
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
