# Meiti V4.4.4 State

Scope: Xiaohongshu / Douyin / Kuaishou / Xianyu
Creative Provider: Lechuang
Postiz: REMOVED

Architecture: PASS
Production Runtime: PASS
Production Store: PASS
Credential Store: MEITI_SECRET_DIR required
OAuth State: PASS
Capability Verification: layered claimed/authorized/contract_verified/live_verified
Publish Gate: PASS
Scheduler: PASS
Idempotency: PASS
Reconciliation: PASS
Analytics: PASS
Security: PASS

Lechuang: BLOCKED_EXTERNAL until official contract and key
Xiaohongshu: HANDOFF_READY; direct publish BLOCKED_EXTERNAL
Douyin: adapter implemented; real OAuth BLOCKED_EXTERNAL
Kuaishou: adapter implemented; real OAuth BLOCKED_EXTERNAL
Xianyu: listing model implemented; JUSHITA/media/listing BLOCKED_EXTERNAL
Real Creative E2E: BLOCKED_EXTERNAL
Real Social E2E: BLOCKED_EXTERNAL
