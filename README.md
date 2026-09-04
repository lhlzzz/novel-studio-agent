# Meiti V4.8

Meiti is prompt-first.

Meiti is an AI Creator Operating System: Creator Brain + Prompt Compiler +
Asset / Continuity / Learning System. External generation can be manual.
Lechuang is a manual creative execution tool unless a verified API adapter
exists. The system never fabricates external generation evidence. grok-4.6
is the engineering agent for this repository, not a video generation model.

```text
Meiti = Creator Brain + Prompt Compiler + Asset/Continuity/Learning System
Lechuang = manual image / video execution tool (API only when verified)
Xiaohongshu = Handoff
Douyin = Native API
Kuaishou = Native API
Xianyu = Commerce listing
Postiz = does not exist
```

```text
User -> Intent -> AccountContext
-> Platform Character / World / Creative DNA / Learning DNA
-> PostgreSQL operational state
-> Obsidian knowledge brain
-> pgvector retrieval (account + platform + GLOBAL only)
-> PromptCompiler -> COPY READY PromptPackage
-> Human Lechuang execution
-> creative import-asset (EXISTING_ASSET / lineage / QA)
-> MediaAsset -> Technical QA -> ContentPackage
-> Publish Gate -> DistributionJob
-> CN Social Provider Resolver
-> XHS Handoff / Douyin Publication / Kuaishou Publication / Xianyu Listing
-> Reconciliation -> Analytics -> MemoryService writeback
-> Next Prompt
```

Creative never publishes. Social never generates media. Handoff is not a
Publication. Content is not commerce. Listing is not a social post. Each
platform account owns its own character, world, asset pool, and learning.
Old assets may be references; a new episode requires a new primary asset.

## Production composition

`SocialRuntime.production()` is the unique production composition root.
CLI, API, workers, Doctor, Control Plane, Scheduler, Reconciliation, and
Analytics take store/secrets from that runtime. Testing uses
`SocialRuntime.testing()`. Production refuses `InMemoryStore` and missing
`MEITI_SECRET_DIR`.

```bash
python scripts/meiti.py bootstrap-production
```

V4.8 hardens the real creator production loop on the V4.7.1 asset DNA. MemoryService owns retrieval and writeback,
Obsidian is the knowledge brain, PostgreSQL stays operational state,
AccountContext is explicit, and PromptCompiler is the human-execution creative
bridge. Unverified video APIs stay NOT_VERIFIED. Bootstrap remains read-only
preflight and never writes credentials.

## Current production set

- 小红书: official OAuth method inventory exists (`auth_info`, `authorize`,
  `access_token`, `refresh_token`, `token_status`, `batch_get_min_user_info`).
  `write_notes` is not live-verified. Meiti prepares a note package and
  persists one `XHSHandoff` per `DistributionJob`. Direct publish is
  BLOCKED_EXTERNAL. Remote reconciliation is NOT_APPLICABLE. Account status
  is `HANDOFF_READY`.
- 抖音: official OAuth + video/image upload + create. HTTP 200 create is
  SUBMITTED/PROCESSING, not PUBLISHED. Chunk upload is suggested above 50MB
  and required above 128MB, max 4GB. PKCE is not part of the official Douyin
  token exchange.
- 快手: official `user_video_publish` (`start_upload` -> runtime HTTPS upload
  -> multipart publish -> photo_id -> photo_info). Whole-file threshold is
  10MB. Publish success is PROCESSING until photo query. PKCE is not used.
- 闲鱼: marketplace listing, not a social post. Listing states are DRAFT /
  SUBMITTED / PUBLISHED / OFF_SHELF / FAILED / UNKNOWN. Production listing
  requires `MEITI_XIANYU_DEPLOYMENT_MODE=JUSHITA`, explicit `CommerceDecision`,
  remote media identifiers, and price/quantity/category validation.

Do not claim production verified or real E2E unless evidence exists in
`docs/audits/meiti-v4.5.4-real-e2e.json`. Missing credentials are
`BLOCKED_EXTERNAL`, not PASS. Image and video gates are independent.

```bash
python -m pytest
python scripts/social_doctor.py
python scripts/meiti_doctor.py
python scripts/meiti.py bootstrap-production
python scripts/runtime_check.py
python scripts/db/migrate.py verify
python -m scripts.meiti social doctor
```
