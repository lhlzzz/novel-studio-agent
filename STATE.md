# Meiti V4.1 State

Creative Runtime: PASS
Lechuang: BLOCKED
Real Judge: BLOCKED
Render: PASS
Persistence: PASS
Resume: PASS

- CreativeWorkflow is the canonical media production abstraction.
- PostgreSQL is the creative source of truth; workers resume from durable state.
- Assets are immutable and keyed by sha256.
- Render uses ffmpeg and writes a new hashed file.
- Visual AI Judge requires a verified vision provider; otherwise BLOCKED.
- Lechuang live calls are BLOCKED until the official API schema is extracted.
- Mock generation is tests-only and is never reported as live.
- Postiz remains the distribution provider behind ProviderResolver and Gate.
