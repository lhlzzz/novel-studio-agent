# Meiti V4.7 Task

**GOAL:** Close Memory, Account, Continuity, Creative, and Video into one
production loop. MemoryService owns retrieval/writeback. Obsidian is the
knowledge brain. PostgreSQL is operational state. Video is xAI
`grok-imagine-video-1.5`. Live video E2E stays NOT_VERIFIED without a real API
MediaAsset + TechnicalQA. Do not fake REAL_VIDEO_E2E=PASS.

**VERIFY:** pytest, architecture tests, bootstrap-production, social_doctor,
meiti_doctor --gate architecture. Production gate exits non-zero until live
evidence exists.

## Current boundary

- Research remains read-only intelligence and is unavailable without credentials.
- Creative live image: BLOCKED_EXTERNAL until real Xiaole image E2E (MediaAsset + TechnicalQA).
- Creative live video: NOT_VERIFIED. Do not guess a video API. Independent from image.
- AI Judge: BLOCKED_EXTERNAL until a verified vision provider exists.
- Distribution live publish: BLOCKED_EXTERNAL until native OAuth + verified account.
- XHS remains HANDOFF_ONLY until write_notes is live-verified.
- Content first. Product is optional and only when CommerceDecision is explicit.
