# Meiti V3 Rules

Meiti is the single owner of the AI Creator / Media Operating System.
Platforms are integrations and adapters only; they are never agents,
workspaces, or independent business databases.

All external actions must pass governance and use `distribution-agent`.
Content packages, distribution jobs, accounts, integrations, commerce actions,
and evidence are separate governed objects. A failed check is `BLOCKED`.

Postiz owns OAuth, uploads, scheduling, publishing, channel settings, and
distribution analytics for verified integrations. Meiti owns business
intelligence, content, memory, strategy, commerce, analytics, and gates.
Postiz must not be copied into this repository or mixed with Meiti's database.

Research is read-only intelligence. Unsupported capabilities return
`unsupported`; they are never simulated.

The PostgreSQL + pgvector database at the configured Meiti URL remains the
source of truth for production data. Obsidian is an operational knowledge
surface, not a second database.
