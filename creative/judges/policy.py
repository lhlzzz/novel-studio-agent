"""Commercial / platform policy gate. Separate from content fit."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from creative.schemas import JudgeResult, utcnow

HARD_SELL = ("buy now", "limited time", "discount", "promo code", "shop now", "click the link")
CTA = ("link in bio", "follow me", "subscribe", "comment yes", "dm me")
SPAM = ("asdf", "!!!!!", "free money")


class ContentPolicyGate:
    name = "policy"

    def evaluate(self, context: dict[str, Any] | None = None, *, asset=None) -> JudgeResult:
        context = context or {}
        text = " ".join(str(context.get(key) or "") for key in ("brief", "caption", "title", "body", "script")).lower()
        intent = str(context.get("commerce_intent") or "none").lower()
        reasons: list[str] = []
        breakdown = {"hard_sell": 100.0, "cta": 100.0, "spam": 100.0, "platform_policy": 100.0}
        if intent not in {"", "none"} and any(token in text for token in HARD_SELL):
            breakdown["hard_sell"] = 0.0
            reasons.append("fail: hard sell")
        if any(token in text for token in CTA) and intent in {"", "none"}:
            breakdown["cta"] = 40.0
            reasons.append("cta without declared commerce intent")
        if any(token in text for token in SPAM):
            breakdown["spam"] = 0.0
            reasons.append("fail: spam")
        if context.get("content_first") is False and intent not in {"", "none"}:
            breakdown["platform_policy"] = 40.0
            reasons.append("fail: commercial intent without content-first brief")
        score = sum(breakdown.values()) / len(breakdown)
        blocked = any(item.startswith("fail:") for item in reasons)
        if blocked:
            score = min(score, 40.0)
        return JudgeResult(
            score=round(score, 2),
            decision="BLOCK" if blocked else "PASS" if score >= 70 else "FAIL",
            reasons=tuple(reasons),
            judge_type=self.name,
            judge_model="policy",
            judge_version="v1",
            breakdown=breakdown,
            timestamp=utcnow(),
            asset_id=getattr(asset, "asset_id", None),
            judge_id=uuid4().hex,
            judge_provider="policy",
        )
