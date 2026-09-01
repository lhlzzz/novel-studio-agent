"""Select research skills dynamically. Missing credentials make research unavailable."""

from __future__ import annotations

import os
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from dataclasses import dataclass, field
from uuid import uuid4
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


class ResearchError(RuntimeError):
    """A live research request failed and produced no validated evidence."""


@dataclass(frozen=True)
class ResearchRequest:
    kind: str
    platform: str = "tiktok"
    handle: str | None = None
    url: str | None = None
    region: str = "US"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchArtifact:
    artifact_id: str
    kind: str
    provider: str
    claims: tuple[ResearchClaim, ...]
    created_at: str
    endpoint: str = ""
    raw_response: dict[str, Any] | None = None


class ScrapeCreatorsClient:
    """Single read-only HTTP owner for ScrapeCreators research calls."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        opener: Any | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("SCRAPECREATORS_API_KEY", "").strip()
        self.base_url = (base_url or os.getenv("SCRAPECREATORS_API_URL") or "https://api.scrapecreators.com").rstrip("/")
        self.timeout = timeout
        self._opener = opener or urlopen

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.api_key:
            raise ResearchError("SCRAPECREATORS_API_KEY is missing")
        values = {key: value for key, value in (params or {}).items() if value is not None}
        url = f"{self.base_url}{path}"
        if values:
            url = f"{url}?{urlencode(values)}"
        request = Request(url, headers={"Accept": "application/json", "x-api-key": self.api_key}, method="GET")
        try:
            with self._opener(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace") if hasattr(exc, "read") else str(exc)
            raise ResearchError(f"ScrapeCreators GET {path} failed ({exc.code}): {detail[:500]}") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ResearchError(f"ScrapeCreators GET {path} failed: {exc}") from exc


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


def _request_spec(skill: str, task: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    platform = str(task.get("platform") or "tiktok").lower()
    handle = task.get("handle") or task.get("username")
    url = task.get("url") or task.get("profile_url")
    if skill == "trend":
        return "/v1/tiktok/get-trending-feed", {"region": str(task.get("region") or "US")}
    if skill == "outlier":
        if not handle and not url:
            raise ResearchError("outlier workflow requires handle or url")
        endpoints = {
            "tiktok": "/v3/tiktok/profile/videos",
            "instagram": "/v2/instagram/user/posts",
            "youtube": "/v1/youtube/channel/videos",
            "linkedin": "/v1/linkedin/company/posts",
            "x": "/v1/twitter/user/tweets",
            "twitter": "/v1/twitter/user/tweets",
        }
        return endpoints.get(platform, endpoints["tiktok"]), {"handle": handle, "url": url}
    if skill == "audience":
        if not handle:
            raise ResearchError("audience workflow requires handle")
        return "/v1/tiktok/user/audience", {"handle": handle}
    if skill == "competitor":
        if not url and not handle:
            raise ResearchError("competitor workflow requires profile url or handle")
        endpoints = {
            "tiktok": "/v1/tiktok/profile",
            "instagram": "/v1/instagram/profile",
            "youtube": "/v1/youtube/channel",
            "linkedin": "/v1/linkedin/company",
            "x": "/v1/twitter/profile",
            "twitter": "/v1/twitter/profile",
        }
        return endpoints.get(platform, endpoints["tiktok"]), {"handle": handle, "url": url}
    if skill == "comment":
        if not url:
            raise ResearchError("comment workflow requires post url")
        endpoints = {
            "tiktok": "/v1/tiktok/video/comments",
            "youtube": "/v1/youtube/video/comments",
            "instagram": "/v2/instagram/post/comments",
            "facebook": "/v1/facebook/post/comments",
            "reddit": "/v1/reddit/post/comments",
        }
        return endpoints.get(platform, endpoints["youtube"]), {"url": url}
    raise ResearchError(f"live workflow is not implemented for {skill}")


def _claims_from_response(response: Any, *, endpoint: str) -> list[ResearchClaim]:
    now = datetime.now(timezone.utc).isoformat()
    payload = response.get("data") if isinstance(response, dict) and "data" in response else response
    items = payload if isinstance(payload, list) else [payload]
    claims: list[ResearchClaim] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        source = str(item.get("url") or item.get("permalink") or item.get("link") or endpoint)
        subject = item.get("text") or item.get("caption") or item.get("title") or item.get("description")
        if not subject:
            subject = json.dumps(item, ensure_ascii=False, sort_keys=True)[:500]
        claims.append(ResearchClaim(
            source=source,
            retrieved_at=now,
            source_type="scrapecreators_api",
            claim=str(subject),
            confidence=0.8 if source != endpoint else 0.6,
        ))
    return claims


def route_research(task: dict[str, Any], *, client: ScrapeCreatorsClient | None = None) -> dict[str, Any]:
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
            "artifact": None,
        }
    try:
        endpoint, params = _request_spec(skill, task)
        response = (client or ScrapeCreatorsClient(api_key=os.getenv("SCRAPECREATORS_API_KEY"))).get(endpoint, params)
        claims = _claims_from_response(response, endpoint=endpoint)
    except ResearchError as exc:
        return {
            "status": "blocked",
            "reason": str(exc),
            "skill": skill,
            "claims": [],
            "credential": state,
            "publishable": False,
            "artifact": None,
        }
    if not claims:
        return {
            "status": "blocked",
            "reason": "live research returned no evidence",
            "skill": skill,
            "claims": [],
            "credential": state,
            "publishable": False,
            "artifact": None,
        }
    from memory.writeback import write_patterns, write_production

    written = 0
    for claim in claims:
        if claim.confidence >= 0.5:
            written += int(write_patterns({
                "kind": "validated_research",
                "successful_pattern": claim.claim,
                "platform_preference": skill,
                "source": claim.source,
                "confidence": claim.confidence,
            }).get("written") or 0)
    artifact = ResearchArtifact(
        artifact_id=uuid4().hex,
        kind=skill,
        provider="scrapecreators",
        claims=tuple(claims),
        created_at=datetime.now(timezone.utc).isoformat(),
        endpoint=endpoint,
        raw_response=response if isinstance(response, dict) else None,
    )
    write_production({
        "kind": "research_artifact",
        "research": artifact.artifact_id,
        "artifact": artifact.artifact_id,
        "source": "scrapecreators",
        "confidence": 0.8,
    })
    return {
        "status": "ready",
        "skill": skill,
        "credential": state,
        "claims": claims,
        "evidence": [claim.__dict__ for claim in claims],
        "memory_writeback": written,
        "publishable": False,
        "artifact": artifact,
    }
