# Meiti Decisions

- **2026-08-26:** Platform is an integration, not an agent or workspace.
- **2026-08-28:** ProviderResolver is the only distribution routing mechanism.
- **2026-08-29:** ContentPackage, Campaign, Publication, MediaUploadResult,
  and DistributionAttempt are first-class.
- **2026-09-01:** CreativeWorkflow is the canonical media production abstraction.
- **2026-09-01:** Lechuang is a generation provider. Live methods stay BLOCKED
  until the official HTTP contract is extracted.
- **2026-09-03 V4.5.3:** XiaoleAI and Lechuang share one Creative credential
  (`XIAOLEAI_API_KEY` / `XIAOLEAI_BASE_URL`). Image generation is the verified
  OpenAI-compatible contract. Video remains NOT_VERIFIED.
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
- **2026-09-03 V4.5:** Production activation. Secret files use hashed identity
  and directory fsync. AccountManager.get_credentials() is read-only.
  MediaUpload is first-class and persisted by JobStore. Xianyu listing states
  are DRAFT/SUBMITTED/PUBLISHED/OFF_SHELF/FAILED/UNKNOWN. Doctor architecture
  and production gates are separate; production gate exits non-zero until
  real E2E evidence exists. Missing external credentials remain BLOCKED_EXTERNAL.

- **2026-09-03 V4.5.1:** Production activation hardening. bootstrap-production is
  read-only preflight and never writes credentials. Provider status/analytics
  require account_id; adapters do not fall back to the first cached account.
  Doctor probe status is not production readiness. Migration 0010 listing
  remap is upgrade-safe and explicitly not strictly reversible. Production CI
  injects GitHub secrets into process env and uses a runner-local
  MEITI_SECRET_DIR path. Missing external credentials remain BLOCKED_EXTERNAL.
