"""Metadata continuity and cross-account isolation guards."""

from __future__ import annotations

from typing import Any

from content.models import CreativeContext, IsolationError
from content.store import ContinuityStore


class CharacterContinuityQA:
    name = "character_continuity"

    def inspect(self, context: CreativeContext, *, store: ContinuityStore) -> dict[str, Any]:
        failures: list[str] = []
        if not context.character_id:
            return {"decision": "pass", "failures": [], "reason": "no character bound"}
        character = store.get_character(context.character_id, account_id=context.account_id)
        if character is None:
            failures.append("character_missing")
        else:
            if character.account_id != context.account_id:
                failures.append("cross_account_character")
            if int((context.character_context or {}).get("version") or character.version) != character.version:
                failures.append("character_version_mismatch")
            refs = set(character.reference_asset_ids)
            context_refs = set((context.character_context or {}).get("reference_asset_ids") or ())
            if refs and context_refs and refs != context_refs:
                failures.append("reference_asset_mismatch")
            prompt = context.normalized_prompt or ""
            if character.name and character.name not in prompt:
                failures.append("prompt_missing_character_name")
        account = store.get_account(context.account_id)
        if account and account.platform != context.platform:
            failures.append("platform_account_mismatch")
        return {
            "decision": "fail" if failures else "pass",
            "failures": failures,
            "reason": ",".join(failures) if failures else "ok",
        }


class CrossAccountIsolationGuard:
    name = "cross_account_isolation"

    def __init__(self, store: ContinuityStore) -> None:
        self.store = store

    def assert_owned(self, *, account_id: str, character_id: str | None = None, world_id: str | None = None, series_id: str | None = None, episode_id: str | None = None, asset_id: str | None = None, allow_share: bool = False) -> None:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        if character_id:
            self.store.get_character(character_id, account_id=account_id, allow_share=allow_share)
        if world_id:
            self.store.get_world(world_id, account_id=account_id, allow_share=allow_share)
        if series_id:
            self.store.get_series(series_id, account_id=account_id, allow_share=allow_share)
        if episode_id:
            self.store.get_episode(episode_id, account_id=account_id, allow_share=allow_share)
        if asset_id:
            self.store.get_lineage(asset_id, account_id=account_id, allow_share=allow_share)

    def inspect(self, context: CreativeContext) -> dict[str, Any]:
        try:
            self.assert_owned(
                account_id=context.account_id,
                character_id=context.character_id,
                world_id=context.world_id,
                series_id=context.series_id,
                episode_id=context.episode_id,
            )
        except IsolationError as exc:
            return {"decision": "fail", "failures": ["cross_account_read"], "reason": str(exc)}
        if context.character_id:
            character = self.store.get_character(context.character_id, account_id=context.account_id)
            if character and character.account_id != context.account_id:
                return {"decision": "fail", "failures": ["cross_platform_character"], "reason": "character owned by another account"}
        return {"decision": "pass", "failures": [], "reason": "ok"}
