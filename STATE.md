# Meiti V4.8.1 State

Scope: Xiaohongshu / Douyin / Kuaishou / Xianyu
Image / video execution: Lechuang is the primary creative provider. Image API is verified. Video stays NOT_VERIFIED. Manual import is fallback only.
Video API: unverified contracts stay NOT_VERIFIED; grok-4.6 is not a video model
Postiz: REMOVED

V4.5.1 = Production Activation Hardening

Architecture: PASS
Production Runtime: requires MEITI_SECRET_DIR + DatabaseStore
Production Store: PASS when database is reachable
Credential Store: MEITI_SECRET_DIR required (0700/0600, hashed identity)
OAuth State: PASS
Capability Verification: layered claimed/authorized/contract_verified/live_verified
Publish Gate: PASS
Scheduler: PASS
Idempotency: PASS
Reconciliation: account-scoped
Analytics: account-scoped
Security: PASS
Bootstrap: read-only preflight
Production CI: secret injection wired

Lechuang/Xiaole: image contract may exist; production media in V4.7.1 is prompt-first + manual import
PromptCompiler: COPY READY IMAGE / VIDEO / IMAGE_TO_VIDEO packages
Platform DNA: independent character, world, creative DNA, asset pool, learning per PlatformAccount
Asset freshness: new episode requires a new primary asset; same sha256 is EXISTING_ASSET
Memory: MemoryService + KnowledgeBrain + pgvector; process _FACTS removed
Accounts: multiple ACTIVE per platform; current selection is single-value
Episodes: identity/order/lifecycle in PostgreSQL; narrative in Obsidian; create_next_episode is transactional
Xiaohongshu: HANDOFF_ONLY; direct publish BLOCKED_EXTERNAL
Douyin: adapter implemented; real OAuth BLOCKED_EXTERNAL
Kuaishou: adapter implemented; real OAuth BLOCKED_EXTERNAL
Xianyu: listing model implemented; JUSHITA/media/listing BLOCKED_EXTERNAL
Real Creative E2E: IMAGE PASS; VIDEO NOT_VERIFIED
Real Social E2E: BLOCKED_EXTERNAL
Production Gate: BLOCKED_EXTERNAL
CODE_COMPLETE: true
EXTERNAL_READY: false
CORE_PRODUCTION: READY
POST_PRODUCTION: NOT_VERIFIED
FULL_LOOP: NOT_VERIFIED
PRODUCTION_READY: true
NOTE: PRODUCTION_READY is CORE_PRODUCTION only. Analytics, Learning, and real Lechuang/social E2E stay NOT_VERIFIED until operator evidence exists. External APIs do not block the human production chain.
