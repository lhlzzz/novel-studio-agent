# Canonical Owner Map

One responsibility has one canonical writer. Projections may exist, but they
are not the source of truth.

ONE canonical writer per responsibility.

| Responsibility | Canonical owner | Canonical writer | Projection |
| --- | --- | --- | --- |
| Creator Identity | `CreatorAccount` (`PlatformAccount`) | `ContinuityStore.save_account` | AccountProfile / operating state |
| Account | `PlatformAccount` | `ContinuityStore.save_account` | Memory / operating state |
| Platform connection | `PlatformConnection` | `ContinuityStore.save_platform_connection` | SocialAccount |
| Creator strategy | `CreatorStrategy` | `CreatorStrategyService` | Account current_strategy_id |
| Creator state | `CreatorState` | `ContinuityStore.save_creator_state` | AccountOperatingState |
| Content decision | `ContentDecision` | `CreatorBrain.decide` | Episode snapshot |
| Content novelty | `ContentNovelty` | `ContentNoveltyService` | Episode novelty_snapshot |
| Content portfolio | `ContentPortfolio` | `ContentNoveltyService` | content_portfolio_items |
| Production memory | `ProductionMemory` | `ProductionMemoryService` | ContinuityMemory / MemoryService |
| Character | `VirtualCharacter` | `ContinuityStore.save_character` | Character revision |
| World | `AccountWorld` | `ContinuityStore.save_world` | World revision |
| Series | `ContentSeries` | `ContinuityStore.save_series` | Calendar |
| Episode | `Episode` | `ContinuityStore.save_episode` | Operating state |
| Prompt | `PromptPackage` | `PromptCompiler.compile` | Memory writeback |
| Creative provider | `CreativeProvider` | `resolve_creative_provider` | Doctor / capability matrix |
| Creative job | `ProductionRun.creative_job_id` | `ContinuityRuntime.submit_generation` | CreativeTask / dashboard |
| Asset | `MediaAsset` | `PlatformAssetService.import_asset` | Memory writeback |
| Asset lineage | `AssetLineage` | `ContinuityStore.allocate_attempt` | None |
| Production | `ProductionRun` | `ContinuityRuntime` | Dashboard |
| Execution proof | `CreativeExecutionReceipt` | `PlatformAssetService._commit_import` | None |
| Evidence | `ProductionEvidence` | `ContinuityStore.save_evidence` | Audit |
| Package | `ContentPackage` | `ContinuityRuntime.package_from_generation` | Calendar |
| Publication | `Publication` | `ContinuityRuntime.record_publication` | Memory writeback |
| Analytics | `AnalyticsRecord` | `ContinuityRuntime.record_analytics` | Memory / learning |
| Learning | `LearningRecord` | `ContinuityRuntime.record_learning` | `PlatformLearningProfile` only when `VERIFIED` |
| Tasks | `CreatorTask` | `TaskOS` | Operating state |
| Calendar | `ContentCalendarEntry` | `EpisodePlanner.ensure_calendar` | Dashboard |

Rules:

- PostgreSQL is the metadata source of truth.
- Filesystem / object storage is the binary source of truth.
- Memory is projection / cache only.
- `projection != canonical writer`.
- Handoff is not publication.
- Manual analytics is not verified analytics.
- Unverified learning cannot update `PlatformLearningProfile` or PromptCompiler.
