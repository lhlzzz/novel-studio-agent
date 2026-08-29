"""Select research skills dynamically. Missing credentials make research unavailable."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_MAP = {
    "trend": "trend-discovery",
    "outlier": "outlier-post-finder",
    "competitor": "competitor-social-research",
    "comment": "comment-mining",
    "demand": "product-demand-research",
    "creator": "creator-profile-teardown",
    "audience": "audience-research",
    "listen": "social-listening-brief",
    "transcript": "transcript-intelligence",
    "ads": "ad-library-teardown",
    "influencer": "influencer-prospecting",
}

SKILLS_ROOT = Path(__file__).resolve().parents[1] / ".agents/skills/intelligence"


@dataclass(frozen=True)
class ResearchClaim:
    source: str
    retrieved_at: str
    source_type: str
    claim: str
    confidence: float


@dataclass(frozen=True)
class ResearchCredentialState:
    available: bool
    authenticated: bool
    quota: str | None
    last_verified: str | None


def credential_state() -> ResearchCredentialState:
    key = os.getenv("SCRAPECREATORS_API_KEY", "").strip()
    available = bool(key)
    return ResearchCredentialState(
        available=available,
        authenticated=available,
        quota=None,
        last_verified=datetime.now(timezone.utc).isoformat() if available else None,
    )


def select_skill(task: dict[str, Any]) -> str:
    kind = str(task.get("kind") or task.get("intent") or "trend").lower()
    for key, skill in SKILL_MAP.items():
        if key in kind:
            return skill
    return SKILL_MAP["trend"]


def route_research(task: dict[str, Any]) -> dict[str, Any]:
    state = credential_state()
    skill = select_skill(task)
    skill_path = SKILLS_ROOT / skill
    if not state.available:
        return {
            "status": "unavailable",
            "reason": "SCRAPECREATORS_API_KEY is missing",
            "skill": skill,
            "claims": [],
            "credential": state,
            "publishable": False,
        }
    if not skill_path.exists():
        return {
            "status": "unavailable",
            "reason": f"skill not installed: {skill}",
            "skill": skill,
            "claims": [],
            "credential": state,
            "publishable": False,
        }
    claim = ResearchClaim(
        source="scrapecreators",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        source_type="api",
        claim=f"research routed to {skill}",
        confidence=0.4,
    )
    return {
        "status": "ready",
        "skill": skill,
        "credential": state,
        "claims": [claim],
        "publishable": False,
    }
