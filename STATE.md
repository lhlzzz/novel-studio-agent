# Meiti V4.5 State

Scope: Xiaohongshu / Douyin / Kuaishou / Xianyu
Creative Provider: Lechuang
Postiz: REMOVED

Architecture: PASS
Production Runtime: requires MEITI_SECRET_DIR + DatabaseStore
Production Store: PASS when database is reachable
Credential Store: MEITI_SECRET_DIR required (0700/0600, hashed identity)
OAuth State: PASS
Capability Verification: layered claimed/authorized/contract_verified/live_verified
Publish Gate: PASS
Scheduler: PASS
Idempotency: PASS
Reconciliation: PASS
Analytics: PASS
Security: PASS

Lechuang: BLOCKED_EXTERNAL until official contract and key
Xiaohongshu: HANDOFF_ONLY; direct publish BLOCKED_EXTERNAL
Douyin: adapter implemented; real OAuth BLOCKED_EXTERNAL
Kuaishou: adapter implemented; real OAuth BLOCKED_EXTERNAL
Xianyu: listing model implemented; JUSHITA/media/listing BLOCKED_EXTERNAL
Real Creative E2E: BLOCKED_EXTERNAL
Real Social E2E: BLOCKED_EXTERNAL
Production Gate: BLOCKED_EXTERNAL
CODE_COMPLETE: true
EXTERNAL_READY: false
PRODUCTION_READY: false
