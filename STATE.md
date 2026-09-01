# Meiti V4.2 State

Creative Runtime: PASS
Lechuang: BLOCKED
AI Judge: BLOCKED
Render: PASS
Persistence: PASS
Worker lease: PASS
Resume: PASS
Postiz: BLOCKED
Real Creative E2E: BLOCKED
Real Distribution E2E: BLOCKED

- CreativeRuntime is the unique composition root.
- PostgreSQL is the creative metadata source of truth; workers resume from durable leases.
- Assets are immutable and keyed by sha256.
- Render uses ffmpeg and writes a new hashed file.
- Visual AI Judge requires a verified vision provider; otherwise BLOCKED.
- Lechuang live calls are BLOCKED until the official API schema is extracted.
- Mock generation is tests-only and is never reported as live.
- Postiz remains the distribution provider behind ProviderResolver and Gate.
