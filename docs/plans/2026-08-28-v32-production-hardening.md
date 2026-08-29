# Meiti V3.3 Production Creator OS

**Goal:** Finish Meiti as one AI Creator Operating System. Delete leftover architecture. Keep one owner per responsibility. Fail closed. Do not fabricate live Postiz or research results.
**Constraints:** Modify existing owners first. Platform is an integration. No compatibility layer. No hardcoded credentials. YAML cannot enable a provider.
**Out of scope:** Domestic live adapters, DM, auto-replies, auto commerce close.

## Must-Haves

- MH1: DistributionAgent routes only through ProviderResolver and never imports a concrete provider adapter.
- MH2: Capabilities, accounts, media, and publication IDs are runtime-verified and fail-closed.
- MH3: A mock ContentPackage can pass Gate, publish idempotently, persist Publication, reconcile, and ingest analytics snapshots.
- MH4: Meiti Doctor and runtime_check report READY or exact BLOCKED reasons.
- MH5: Real Postiz publish is attempted against a controlled test account, or Overall is NOT_READY with the blocking issue named.

- MH6: ContentPackage, Campaign, Publication, MediaUploadResult, and DistributionAttempt are first-class objects, not metadata dumps.
- MH7: Control Plane and Doctor report PASS/WARN/BLOCKED with `{ready, checks}`.
- MH8: Tests live under unit/integration/architecture/e2e/fixtures and include the V3.3 architecture names.
- MH9: Production migrations do not write demo rows. Seed stays in tests/fixtures.

### Task 1: Baseline and residue
- [ ] Confirm main at baseline SHA, no workspaces tree, pytest baseline recorded
- [ ] Remove leftover architecture residue
- **Verification:** architecture tests pass

### Task 2: Agent runtime registry
- [ ] Upgrade agents/registry.yaml into resolve_agent()
- [ ] Give every agent directory an executable runtime contract
- **Verification:** resolve_agent returns implementation, owner, capabilities, status

### Task 3: ProviderResolver
- [ ] Add integrations/providers/resolver.py
- [ ] DistributionAgent uses resolver, not PostizAdapter import
- **Verification:** test_distribution_agent_does_not_import_postiz_adapter_directly

### Task 4: Integration states and capability verification
- [ ] Integration lifecycle states; yaml cannot set enabled=true
- [ ] Capability records with supported/verified/verified_at/method
- **Verification:** unverified capability blocks publish

### Task 5: Postiz client production hardening
- [ ] health()/is-connected(); typed errors; retry/backoff; Retry-After
- **Verification:** retryable vs permanent errors are distinguishable

### Task 6: Media upload and cache
- [ ] Upload before create_post; MediaUploadResult; sha256 cache
- **Verification:** local uuid+path media objects are rejected

### Task 7: Variants, jobs, idempotency, queue
- [ ] Platform ContentVariant; job state machine; idempotency_key; queue/dead-letter
- **Verification:** duplicate publish is idempotent; illegal transitions rejected

### Task 8: Gate, publication persistence, external IDs
- [ ] Extra gate checks; persist Publication; separate job/provider/platform IDs
- **Verification:** publication persisted; IDs not reused

### Task 9: Reconciliation and analytics loop
- [ ] Reconciliation service+worker; metric snapshots; analytics worker; insights; experiments; memory write-back
- **Verification:** mock E2E analytics loop and reconciliation tests

### Task 10: Memory retrieval, KG, research, commerce
- [ ] retrieve-before-generate; KG relation types; research router+credentials+evidence; ContentProductLink analytics
- **Verification:** research unavailable without credential; content != product

### Task 11: Doctor, runtime_check, mock E2E, docs
- [ ] scripts/meiti_doctor.py and runtime_check.py; mock E2E; AGENTS.md contract additions
- **Verification:** pytest 0 failed; runtime_check JSON; compileall

### Task 12: Real Postiz activation and readiness report
- [ ] Start/auth Postiz, discover one overseas account, Gate-approved test publish if possible
- [ ] Refresh understand-anything graph
- **Verification:** READY or NOT_READY with exact blocking issues

### Task 13: ContentPackage v2, Campaign, StrategyPlan
- [ ] First-class ContentPackage fields; Campaign object; StrategyPlan output
- **Verification:** content tests construct packages without stuffing required fields into metadata

### Task 14: Provider-neutral contracts and attempts
- [ ] MediaUploadResult and Publication drop Postiz field names
- [ ] DistributionAttempt, request_id, adapter authenticate/health/upload_media/cancel
- [ ] DistributionService does not import Postiz errors
- [ ] Delete adapters/postiz compatibility re-export
- **Verification:** architecture tests for IDs, media upload, gate, and no Postiz import

### Task 15: Control plane, doctor, observability
- [ ] Control Plane snapshot of agents/integrations/jobs/workers/database
- [ ] Doctor JSON `{ready, checks}` covering required subsystems
- [ ] Structured logs with secret redaction
- **Verification:** runtime_check JSON; architecture test_no_secret_logging

### Task 16: Versioned migrations without production demo seed
- [ ] schema_migrations + upgrade/history on existing migrate.py owner
- [ ] bootstrap/verify do not require meiti-demo-* rows
- [ ] Demo fixtures live under tests/fixtures
- **Verification:** migrate.py upgrade/history/verify; no demo write on init

### Task 17: Test layout and architecture invariants
- [ ] Move tests into unit/integration/architecture/e2e/fixtures
- [ ] Add the required architecture test names
- **Verification:** pytest collects and passes the named architecture tests

### Task 18: Docs describe current architecture
- [ ] Rewrite AGENTS.md RULES.md README.md STATE.md TASK.md TOOLING.md DECISIONS.md HANDOFF.md NEXT_ACTION.md
- [ ] RULES.md contains the 20 architecture rules
- **Verification:** docs mention ProviderResolver, Publication, Control Plane; no per-platform backend ports

### Task 19: Mock path green
- [ ] pytest, compileall, doctor, runtime_check
- **Verification:** pytest 0 failed on mock path

### Task 20: Real Postiz/research attempt, graph, commit, report
- [ ] Attempt Postiz stack/auth; attempt live research; refresh graph; commit
- **Verification:** READY or NOT_READY with exact blocking issues
