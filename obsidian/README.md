# Meiti Knowledge Brain

Obsidian is Meiti's second brain. PostgreSQL remains the operational source of truth.

Do not store episode numbers, publication status, workflow status, or provider request ids here as the system of record. Those live in PostgreSQL.

```text
obsidian/
  accounts/      Account Knowledge
  characters/    Character Knowledge
  worlds/        World Knowledge
  series/        Series Lore
  episodes/      Episode Narrative
  strategy/      Content Strategy
  platforms/     Platform Insights
  research/      Research
  learnings/     Successful / failed patterns, production learnings
  decisions/     Creative decisions
  analytics/     Analytics learnings
```

Owner: `memory.brain.KnowledgeBrain`

Write path:

PostgreSQL operational event → MemoryService → KnowledgeProjection → Markdown → embedding index

Obsidian edits may be re-indexed. They must not mutate runtime-critical operational state.
