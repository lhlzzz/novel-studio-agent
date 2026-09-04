---
title: Meiti V4.7 Knowledge Brain
owner: memory.brain.KnowledgeBrain
type: knowledge-brain
version: 4.7
---

# Meiti V4.7 Knowledge Brain

Obsidian is human-readable knowledge. PostgreSQL is operational state. pgvector is retrieval.

## Production loop

User → Intent → AccountContext → PostgreSQL / Obsidian / Retrieval → Strategy → Content → CreativeWorkflow → Provider Resolver (Lechuang image / xAI `grok-imagine-video-1.5`) → MediaAsset → Technical QA → AI Judge → ContentPackage → Platform Variant → Publication → Analytics → MemoryService writeback → Obsidian + pgvector

## Boundaries

- MemoryService is the unique production memory owner.
- KnowledgeDocument is scoped: GLOBAL → PLATFORM → ACCOUNT → CHARACTER → WORLD → SERIES → EPISODE → PUBLICATION / ANALYTICS.
- Account A knowledge never enters Account B retrieval unless scope is GLOBAL.
- Creative never publishes. Social never generates media.
- Video model is `grok-imagine-video-1.5`. Grok 4.6 is not a video model.
