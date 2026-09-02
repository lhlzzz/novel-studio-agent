# Meiti Decisions

- **2026-08-26:** Platform is an integration, not an agent or workspace.
- **2026-08-28:** ProviderResolver is the only distribution routing mechanism.
- **2026-08-29:** ContentPackage, Campaign, Publication, MediaUploadResult,
  and DistributionAttempt are first-class.
- **2026-09-01:** CreativeWorkflow is the canonical media production abstraction.
- **2026-09-01:** Lechuang is a generation provider. Live methods stay BLOCKED
  until the official HTTP contract is extracted.
- **2026-09-02:** Meiti owns native social accounts. Credentials are stored by
  credential_ref only.
- **2026-09-02 V4.4.2:** Production social composition root is
  `SocialRuntime.production()`. Scope is 小红书 / 抖音 / 快手 / 闲鱼.
  XHS is handoff-only. Xianyu is a commerce listing surface that requires
  Jushita. Publish Gate reads runtime truth; callers cannot inject
  verified=true. Scheduler claims durable jobs and publishes; it never calls
  adapter.schedule().
