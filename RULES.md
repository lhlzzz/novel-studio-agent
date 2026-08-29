# Meiti V3 Rules

Meiti is the single owner of the AI Creator Operating System.
Platforms are integrations and adapters only; they are never agents,
workspaces, or independent business databases.

1. Platform is an Integration.
2. Platform is never an Agent.
3. Workspace architecture is forbidden.
4. Distribution has one owner.
5. Provider resolution goes through Registry.
6. DistributionAgent never imports concrete adapters.
7. External actions require Publish Gate.
8. Provider capabilities require verification.
9. Media must be uploaded before provider publish when required.
10. Successful external actions create Publication.
11. Publication IDs are never conflated.
12. Every external action is idempotent.
13. Failed operations are retry-safe.
14. Permanent failures enter dead-letter state.
15. Analytics flows back into Memory.
16. Memory flows into Strategy.
17. Commerce is decoupled from Content.
18. Secrets never enter source control.
19. Research never fabricates live data.
20. No compatibility layer for deleted architecture.

All external actions must pass governance and use `distribution-agent`.
Content packages, campaigns, distribution jobs, attempts, accounts,
integrations, commerce links, and evidence are separate governed objects.
A failed check is `BLOCKED`.

ProviderResolver is the only provider routing mechanism. Capabilities, media,
and accounts require runtime verification. Publish is idempotent. Publications
persist distinct job, provider, and platform IDs. Scheduled and published
jobs are reconciled. Analytics snapshots flow back into memory.

Postiz owns OAuth, uploads, scheduling, publishing, channel settings, and
distribution analytics for verified integrations. Meiti owns business
intelligence, content, memory, strategy, commerce, analytics, and gates.
Postiz must not be copied into this repository or mixed with Meiti's database.

Research is read-only intelligence. Unsupported capabilities return
`unsupported`; they are never simulated.

The PostgreSQL + pgvector database at the configured Meiti URL remains the
source of truth for production data. Obsidian is an operational knowledge
surface, not a second database.
