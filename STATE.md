# Meiti V4.4 State

Creative Runtime: PASS
Lechuang: BLOCKED
AI Judge: BLOCKED
Render: PASS
Persistence: PASS
Worker lease: PASS
Resume: PASS
Social Provider Registry: PASS
Social Account Manager: PASS
Real Social Accounts: BLOCKED
Real Creative E2E: BLOCKED
Real Distribution E2E: BLOCKED

- CreativeRuntime is the unique composition root.
- PostgreSQL is the creative and social metadata source of truth; workers resume from durable leases.
- Assets are immutable and keyed by sha256.
- Render uses ffmpeg and writes a new hashed file.
- Visual AI Judge requires a verified vision provider; otherwise BLOCKED.
- Lechuang live calls are BLOCKED until the official API schema is extracted.
- Mock generation is tests-only and is never reported as live.
- Native social adapters sit behind SocialProviderResolver and Gate.
- Real platform ENABLE requires verified OAuth credentials.

- V4.4 removes third-party social schedulers. Live READY requires real Lechuang, Vision, native social OAuth, Research, and E2E evidence.
- AI Gateway is a separate vision provider from Lechuang. Credential reuse is allowed; identity is not merged.
- Doctor reports BLOCKED instead of PASS when keys, contracts, or real publications are missing.
