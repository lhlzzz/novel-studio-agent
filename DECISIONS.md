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
- **2026-09-03 V4.5.4:** Creative production gates are capability-independent.
  IMAGE_PRODUCTION_READY does not require video. VIDEO and IMAGE_TO_VIDEO stay
  NOT_VERIFIED until a real video API contract exists. Do not guess endpoints.
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
- **2026-09-04 V4.6:** PlatformAccount is the isolation boundary. VirtualCharacter
  and AccountWorld are first-class, account-scoped entities. Series and Episode
  live in PostgreSQL. ContinuityEngine builds CreativeContext. Same campaign
  produces independent platform ContentPackages. MediaAsset lineage is required.
  Lechuang remains the only generation provider. Video stays NOT_VERIFIED.
- **2026-09-04 V4.7.1:** Meiti is prompt-first. Each PlatformAccount owns an
  independent character, world, creative DNA, learning DNA, and asset pool.
  Production primary assets require account_id + platform. CREATE/CONTINUE/
  GENERATE episodes require a new primary asset; same sha256 is the same
  immutable asset (EXISTING_ASSET), not a new identity. Cross-platform primary
  reuse is forbidden; reference and derived lineage are allowed. PromptCompiler
  outputs COPY READY packages for Lechuang execution. grok-4.6 is the
  engineering agent, never a video generation model. Unverified video APIs stay
  NOT_VERIFIED. The system never fabricates external generation evidence.
- **2026-09-05 V5.1:** Lechuang is the primary creative provider. XiaoleAI and
  Lechuang share `XIAOLEAI_API_KEY`. Image `POST /images/generations` is the
  verified contract. Video stays NOT_VERIFIED. Creator OS `today` / `continue`
  compile a PromptPackage, submit a CreativeJob, and import through
  `PlatformAssetService`. Manual import remains a fallback, not the default
  image path. Social OAuth is not required for generation.
- **2026-09-06:** Lechuang video follows the official XiaoleAI contract:
  `POST /videos`, `GET /videos/{id}`, `GET /videos/{id}/content`. Meiti does
  not keep `/image/created` or `/created/video` as fallback. Video is
  documented and executable, but stays NOT_VERIFIED until live MediaAsset +
  TechnicalQA succeeds. Do not fake PASS.
- **2026-09-06:** Lechuang is the only Creative Provider. Image, video, and
  image-to-video all execute through `LechuangAdapter` / `LechuangClient`.
  The parallel xAI creative provider (`grok-imagine-video-1.5`,
  `/videos/generations`) is removed. Social providers are unchanged.
