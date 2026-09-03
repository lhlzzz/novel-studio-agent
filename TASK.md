# Meiti V4.5.4 Task

**GOAL:** Production activation hardening. Architecture, persistence, secret
store, account-scoped reconciliation, doctor probe/gate split, CI secret
injection, and bootstrap preflight are code-complete. Live provider E2E stays
BLOCKED_EXTERNAL without real credentials.

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
