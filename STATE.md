# Meiti V4.7 State

Scope: Xiaohongshu / Douyin / Kuaishou / Xianyu
Image Provider: Lechuang
Video Provider: xAI grok-imagine-video-1.5 (contract implemented, live E2E NOT_VERIFIED)
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

Lechuang/Xiaole: image contract verified; real image E2E depends on live evidence; video is owned by xAI, not Lechuang
xAI video: grok-imagine-video-1.5; VIDEO_CONTRACT_VERIFIED=False until real MediaAsset + TechnicalQA
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
PRODUCTION_READY: false
