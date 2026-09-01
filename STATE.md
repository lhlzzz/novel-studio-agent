# Meiti V4 State

- Creative Workflow Engine is the media production owner.
- MediaAgent selects workflows and does not import LechuangAdapter.
- Lechuang is a generation provider with a typed contract. Live calls are
  BLOCKED until the official API schema is extracted and authenticated.
- Mock creative path: Brief -> Workflow -> Fake Lechuang -> Image/Judge ->
  Video/Judge -> MediaAsset -> ContentPackage.
- Assets are immutable and keyed by sha256.
- Async generation is polled by `services.workers.creative_worker`, not agents.
- Postiz remains the distribution provider behind ProviderResolver and Gate.
- DistributionAgent does not import PostizAdapter.
- Mock E2E covers creative packaging and Postiz dry-run/publish loops.
- Real Lechuang generation is BLOCKED without a verified contract and key.
- Real Postiz publish is BLOCKED without POSTIZ_API_KEY, a running Postiz
  process, and one verified overseas account.

MEITI V4 Architecture Ready. Creative live execution = BLOCKED.
Distribution live execution = BLOCKED.
