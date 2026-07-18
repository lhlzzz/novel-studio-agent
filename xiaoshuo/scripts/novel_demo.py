#!/usr/bin/env python3
"""Deterministic, offline novel-writing workflow demo."""
from __future__ import annotations

import json


def build_story() -> dict:
    chapters = [
        "Debt notice interrupts a production outage.",
        "The protagonist finds a legacy bug tied to a vanished founder.",
        "A midnight fix saves a client and exposes a larger fraud.",
        "The first contract buys time but creates a rival.",
        "The team forms around an impossible migration.",
        "A public failure becomes the midpoint reversal.",
        "Evidence points back to the original debt.",
        "The rival offers a deal with a hidden cost.",
        "The final release becomes a live courtroom.",
        "The debt is cleared; the new company ships its first product.",
    ]
    return {
        "premise": "A debt-ridden programmer discovers that fixing a legacy production bug can expose the scheme that ruined his family.",
        "characters": [
            {"name": "Lin Zhou", "role": "backend engineer", "want": "clear a three-million debt"},
            {"name": "Su Yan", "role": "SRE lead", "want": "prove she can lead a rescue"},
            {"name": "Gu Han", "role": "former founder", "want": "keep the old system buried"},
        ],
        "outline": [{"chapter": index + 1, "beat": beat} for index, beat in enumerate(chapters)],
        "chapter_1_excerpt": "At 02:17, the pager rang before the debt collector did. Lin Zhou opened the incident panel, saw a payment queue frozen at zero, and understood that one broken line of code might be worth more than every apology he had left.",
        "quality_gates": {"hook_in_first_page": True, "clear_protagonist_goal": True, "escalating_stakes": True, "chapter_cliffhanger": True},
    }


if __name__ == "__main__":
    print(json.dumps(build_story(), indent=2))
