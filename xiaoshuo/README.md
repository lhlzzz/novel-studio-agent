# Novel Studio

An offline novel-writing workflow that produces a premise, character set, ten-chapter outline, opening excerpt, and quality gates for a specified story direction.

## Demo

```bash
python scripts/novel_demo.py
```

The demo emits stable JSON for the "programmer debt comeback" urban web-fiction concept and needs no model key or external service.

## Workflow

1. Define premise, audience, and genre constraints.
2. Create the story bible and escalating chapter beats.
3. Generate an opening excerpt.
4. Run quality gates for hook, protagonist goal, stakes, and chapter cliffhanger.

## Evidence

Existing content and writing references remain under `写作手法/`, `我欠三百万，修bug续命/`, and `enterprise-doctor/`. The database layer in `scripts/db/` is state infrastructure, not the product claim.

## Validation

```bash
python scripts/novel_demo.py
python scripts/db/migrate.py verify
```

## Limitations

This deterministic demo illustrates workflow shape. It is not a replacement for iterative author review or an LLM-backed drafting pipeline.
