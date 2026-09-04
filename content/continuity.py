"""Continuity engine. Episode history lives in the database, not chat context."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from content.models import (
    AccountWorld,
    ContinuityError,
    ContinuityMemory,
    CreativeContext,
    Episode,
    IsolationError,
    ResolvedTarget,
    VirtualCharacter,
    utcnow,
)
from content.platform_policy import platform_policy
from content.store import ContinuityStore


class ContinuityEngine:
    def __init__(self, store: ContinuityStore | None = None) -> None:
        self.store = store or ContinuityStore()

    def get_previous_episode(self, episode: Episode) -> Episode | None:
        if not episode.previous_episode_id:
            return None
        previous = self.store.get_episode(episode.previous_episode_id, account_id=episode.account_id)
        if previous is None:
            raise ContinuityError(f"previous episode {episode.previous_episode_id} is missing for {episode.episode_id}")
        return previous

    def get_next_episode(self, episode: Episode) -> Episode | None:
        if not episode.next_episode_id:
            return None
        nxt = self.store.get_episode(episode.next_episode_id, account_id=episode.account_id)
        if nxt is None:
            raise ContinuityError(f"next episode {episode.next_episode_id} is missing for {episode.episode_id}")
        return nxt

    def latest_episode(self, series_id: str, *, account_id: str) -> Episode | None:
        series = self.store.get_series(series_id, account_id=account_id)
        if series is None:
            raise IsolationError(f"series {series_id} is not owned by {account_id}")
        return self.store.latest_episode(series.series_id)

    def extract_character_state(self, episode: Episode, character: VirtualCharacter | None) -> dict[str, Any]:
        state = dict(episode.character_state or {})
        if character is None:
            return state
        state.setdefault("character_id", character.character_id)
        state.setdefault("version", character.version)
        state.setdefault("name", character.name)
        state.setdefault("clothing", dict(character.clothing_profile))
        state.setdefault("hair", dict(character.hair_profile))
        state.setdefault("body", dict(character.body_profile))
        state.setdefault("face", dict(character.face_profile))
        return state

    def extract_visual_state(self, episode: Episode, world: AccountWorld | None) -> dict[str, Any]:
        state = dict(episode.visual_state or {})
        if world is not None:
            state.setdefault("visual_language", dict(world.visual_language))
            state.setdefault("tone", world.tone)
        return state

    def extract_story_state(self, episode: Episode) -> dict[str, Any]:
        state = dict(episode.story_state or {})
        state.setdefault("title", episode.title)
        state.setdefault("brief", episode.brief)
        state.setdefault("episode_no", episode.episode_no)
        return state

    def validate_continuity(self, episode: Episode) -> list[str]:
        failures: list[str] = []
        series = self.store.get_series(episode.series_id, account_id=episode.account_id)
        if series is None:
            failures.append("series_missing")
            return failures
        if episode.episode_no > 1:
            if not episode.previous_episode_id:
                failures.append("previous_episode_id_missing")
            else:
                previous = self.store.get_episode(episode.previous_episode_id, account_id=episode.account_id)
                if previous is None:
                    failures.append("previous_episode_missing")
                elif previous.episode_no != episode.episode_no - 1:
                    failures.append("previous_episode_out_of_order")
                elif previous.series_id != episode.series_id:
                    failures.append("previous_episode_wrong_series")
        return failures

    def create_next_episode(self, series_id: str, *, account_id: str, title: str = "", brief: str = "") -> Episode:
        series = self.store.get_series(series_id, account_id=account_id)
        if series is None:
            raise IsolationError(f"series {series_id} is not owned by {account_id}")
        previous = self.store.latest_episode(series.series_id)
        episode_no = (previous.episode_no + 1) if previous else 1
        if previous is not None:
            failures = self.validate_continuity(previous)
            if failures and previous.episode_no > 1:
                raise ContinuityError("cannot continue: " + ",".join(failures))
        account = self.store.get_account(account_id)
        character = None
        if account and account.character_id:
            character = self.store.get_character(account.character_id, account_id=account_id)
        world = None
        if series.world_id:
            world = self.store.get_world(series.world_id, account_id=account_id)
        episode = Episode(
            episode_id=uuid4().hex,
            series_id=series.series_id,
            episode_no=episode_no,
            title=title or (brief[:40] if brief else f"Day {episode_no}"),
            brief=brief,
            previous_episode_id=previous.episode_id if previous else None,
            continuity_context=self.build_continuity_context(previous) if previous else {},
            character_state=self.extract_character_state(previous, character) if previous else self.extract_character_state(Episode(episode_id="seed", series_id=series.series_id, episode_no=0, account_id=account_id), character),
            world_state={"world_id": world.world_id, "name": world.name} if world else {},
            location_state=dict((previous.location_state if previous else {}) or {}),
            visual_state=self.extract_visual_state(previous, world) if previous else self.extract_visual_state(Episode(episode_id="seed", series_id=series.series_id, episode_no=0, account_id=account_id), world),
            story_state=self.extract_story_state(previous) if previous else {},
            content_status="BRIEFED",
            account_id=account_id,
        )
        saved = self.store.save_episode(episode)
        if previous is not None:
            self.store.save_episode(Episode(**{**previous.__dict__, "next_episode_id": saved.episode_id, "updated_at": utcnow()}))
        self.store.save_series(type(series)(**{**series.__dict__, "current_episode_no": saved.episode_no, "updated_at": utcnow()}))
        return saved

    def build_continuity_context(self, previous: Episode | None) -> dict[str, Any]:
        if previous is None:
            return {}
        failures = self.validate_continuity(previous) if previous.episode_no > 1 else []
        if failures:
            raise ContinuityError("continuity broken: " + ",".join(failures))
        return {
            "previous_episode_id": previous.episode_id,
            "previous_episode_no": previous.episode_no,
            "previous_title": previous.title,
            "previous_brief": previous.brief,
            "character_state": dict(previous.character_state or {}),
            "world_state": dict(previous.world_state or {}),
            "location_state": dict(previous.location_state or {}),
            "visual_state": dict(previous.visual_state or {}),
            "story_state": dict(previous.story_state or {}),
            "content_package_id": previous.content_package_id,
        }

    def build_creative_context(
        self,
        *,
        target: ResolvedTarget,
        request: str,
        brief: str = "",
        extras: dict[str, Any] | None = None,
    ) -> CreativeContext:
        account = self.store.get_account(target.account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {target.account_id}")
        if account.platform != target.platform:
            raise IsolationError(f"account {account.account_id} is {account.platform}, not {target.platform}")
        character = None
        if account.character_id:
            character = self.store.get_character(account.character_id, account_id=account.account_id)
        world = None
        if account.world_id:
            world = self.store.get_world(account.world_id, account_id=account.account_id)
        series = None
        if target.series_id:
            series = self.store.get_series(target.series_id, account_id=account.account_id)
        episode = None
        if target.episode_id:
            episode = self.store.get_episode(target.episode_id, account_id=account.account_id)
        previous = self.get_previous_episode(episode) if episode else None
        continuity = self.build_continuity_context(previous) if previous else (episode.continuity_context if episode else {})
        policy = platform_policy(account.platform)
        extras = dict(extras or {})
        character_context = _character_context(character)
        world_context = _world_context(world)
        prompt = _normalize_prompt(request=request, brief=brief or (episode.brief if episode else ""), character=character, world=world, continuity=continuity, policy=policy)
        context = CreativeContext(
            context_id=uuid4().hex,
            account_id=account.account_id,
            platform=account.platform,
            character_id=character.character_id if character else None,
            world_id=world.world_id if world else None,
            series_id=series.series_id if series else target.series_id,
            episode_id=episode.episode_id if episode else target.episode_id,
            campaign_id=str(extras.get("campaign_id") or "") or None,
            user_request=request,
            creative_request=brief or request,
            normalized_prompt=prompt,
            system_constraints={
                "keep_face_consistent": True,
                "keep_body_consistent": True,
                "keep_age_consistent": True,
                "keep_general_style_consistent": True,
                "forbidden_changes": list(character.forbidden_changes) if character else [],
            },
            character_context=character_context,
            world_context=world_context,
            continuity_context=dict(continuity or {}),
            platform_context=policy,
            generation_parameters=dict(extras.get("generation_parameters") or {}),
            provider=str(extras.get("provider") or ""),
            model=str(extras.get("model") or ""),
            resolved_target=target.as_dict(),
        )
        saved = self.store.save_context(context)
        self._remember(account.account_id, "episode" if episode else "account", (episode.episode_id if episode else account.account_id), "last_context_id", saved.context_id)
        return saved

    def _remember(self, account_id: str, kind: str, subject_id: str, key: str, value: Any) -> None:
        self.store.save_memory(ContinuityMemory(
            memory_id=uuid4().hex,
            kind=kind,
            account_id=account_id,
            subject_id=subject_id,
            key=key,
            value=value,
        ))


def _character_context(character: VirtualCharacter | None) -> dict[str, Any]:
    if character is None:
        return {}
    return {
        "character_id": character.character_id,
        "version": character.version,
        "name": character.name,
        "gender": character.gender,
        "age_range": character.age_range,
        "appearance_profile": dict(character.appearance_profile),
        "body_profile": dict(character.body_profile),
        "face_profile": dict(character.face_profile),
        "hair_profile": dict(character.hair_profile),
        "skin_profile": dict(character.skin_profile),
        "clothing_profile": dict(character.clothing_profile),
        "personality_profile": dict(character.personality_profile),
        "background_story": character.background_story,
        "speaking_style": character.speaking_style,
        "behavioral_traits": list(character.behavioral_traits),
        "visual_identity_rules": dict(character.visual_identity_rules),
        "forbidden_changes": list(character.forbidden_changes),
        "reference_asset_ids": list(character.reference_asset_ids),
    }


def _world_context(world: AccountWorld | None) -> dict[str, Any]:
    if world is None:
        return {}
    return {
        "world_id": world.world_id,
        "name": world.name,
        "world_description": world.world_description,
        "core_theme": world.core_theme,
        "values": list(world.values),
        "tone": world.tone,
        "visual_language": dict(world.visual_language),
        "locations": list(world.locations),
        "daily_life_rules": list(world.daily_life_rules),
        "story_rules": list(world.story_rules),
        "audience": world.audience,
        "taboos": list(world.taboos),
        "brand_rules": list(world.brand_rules),
    }


def _normalize_prompt(*, request: str, brief: str, character: VirtualCharacter | None, world: AccountWorld | None, continuity: dict[str, Any], policy: dict[str, Any]) -> str:
    parts = [brief or request]
    if character:
        parts.append(f"Character {character.name}, {character.gender} {character.age_range}.".strip())
        if character.clothing_profile:
            parts.append("Clothing: " + ", ".join(f"{k}={v}" for k, v in character.clothing_profile.items() if v))
        if character.forbidden_changes:
            parts.append("Do not change: " + "; ".join(character.forbidden_changes))
    if world:
        parts.append(f"World: {world.name}. {world.world_description}".strip())
        if world.visual_language:
            parts.append("Visual: " + ", ".join(f"{k}={v}" for k, v in world.visual_language.items() if v))
    previous_title = continuity.get("previous_title")
    if previous_title:
        parts.append(f"Continue from episode {continuity.get('previous_episode_no')}: {previous_title}.")
    visual = policy.get("visual") or {}
    if visual:
        parts.append("Platform visual: " + ", ".join(str(item) for item in visual.values() if item))
    return " ".join(part for part in parts if part)
