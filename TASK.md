# Meiti V4.5 Task

**GOAL:** Production activation for CN social + Lechuang. Architecture,
persistence, secret store, OAuth, MediaUpload, DistributionOutcome, CI, and
doctor semantics are code-complete. Live provider E2E stays BLOCKED_EXTERNAL
without real credentials.

**VERIFY:** pytest, architecture tests, bootstrap-production, social_doctor,
meiti_doctor --gate architecture. Production gate exits non-zero until live
evidence exists.

## Current boundary

- Research remains read-only intelligence and is unavailable without credentials.
- Creative live generation: BLOCKED_EXTERNAL until Lechuang API contract + key.
- AI Judge: BLOCKED_EXTERNAL until a verified vision provider exists.
- Distribution live publish: BLOCKED_EXTERNAL until native OAuth + verified account.
- XHS remains HANDOFF_ONLY until write_notes is live-verified.
- Content first. Product is optional and only when CommerceDecision is explicit.
