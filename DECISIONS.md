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
- **2026-09-03 V4.4.3:** XHS handoff is a first-class `XHSHandoff`, never a
  Publication. XHS accounts are `HANDOFF_READY`, not `AUTHENTICATED`.
  Production constructors require an explicit store and secret store.
- **2026-09-03 V4.4.4:** Production closure. Distribution returns
  PublicationOutcome | HandoffOutcome | ListingOutcome. Xianyu listing is a
  commerce entity persisted by DistributionService, not the adapter. Xianyu
  local-bytes upload stays unsupported until a verified contract exists.
  Capability records are layered. `_credentials()` is read-only. Refresh is
  account-scoped. Media uploads are keyed by source_hash+provider+account_id.
  request_id, provider_request_id, and provider_object_id are distinct.
  Missing external credentials are BLOCKED_EXTERNAL, never PASS.
