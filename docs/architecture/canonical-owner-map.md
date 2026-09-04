# Canonical Owner Map

One responsibility has one canonical writer. Projections may exist, but they
are not the source of truth.

ONE canonical writer per responsibility.

| Responsibility | Canonical owner | Canonical writer | Projection |
| --- | --- | --- | --- |
| Account | `PlatformAccount` | `ContinuityStore.save_account` | Memory / operating state |
| Character | `VirtualCharacter` | `ContinuityStore.save_character` | Character revision |
| World | `AccountWorld` | `ContinuityStore.save_world` | World revision |
| Series | `ContentSeries` | `ContinuityStore.save_series` | Calendar |
| Episode | `Episode` | `ContinuityStore.save_episode` | Operating state |
| Prompt | `PromptPackage` | `PromptCompiler.compile` | Memory writeback |
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
