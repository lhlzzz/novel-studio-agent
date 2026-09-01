# Meiti V4.2 Decisions

- **2026-08-26:** Platform is an integration, not an agent or workspace.
- **2026-08-26:** Meiti owns business data; Postiz owns distribution infrastructure.
- **2026-08-28:** ProviderResolver is the only distribution routing mechanism.
- **2026-08-29:** ContentPackage, Campaign, Publication, MediaUploadResult,
  and DistributionAttempt are first-class.
- **2026-09-01:** CreativeWorkflow is the canonical media production abstraction.
  Isolated generation scripts are deleted rather than wrapped.
- **2026-09-01:** Lechuang is a generation provider. The official HTTP contract
  was not extractable, so live methods raise ProviderBlocked/UnsupportedCapability.
  Mock generation is the only CI path.
- **2026-09-01:** Providers bind per workflow node, never as a workflow-wide field.
- **2026-09-01:** Default people/lifestyle path is image -> image QA -> image-to-video.
- **2026-09-01:** Generation assets are immutable and content-addressed by sha256.
- **2026-09-01:** Judge returns score/decision/reason and never publishes.

- **2026-09-01:** Creative runtime is durable: PostgreSQL CreativeRun/Task, worker lease, resume, replay from workflow snapshot.
- **2026-09-01:** Per-node provider binding. Immutable assets. sha256 identity. Async worker.
