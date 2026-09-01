# Meiti V4.2 Rules

Meiti is the single owner of the AI Creator Operating System.
Platforms are integrations and adapters only; they are never agents,
workspaces, or independent business databases.

1. Platform is an Integration.
2. Platform is never an Agent.
3. Workspace architecture is forbidden.
4. CreativeWorkflow is the canonical media production abstraction.
5. Provider is an execution backend, never an Agent.
6. Agent selects workflows; workflows execute node graphs.
7. Generation and distribution stay decoupled.
8. Distribution has one owner.
9. Provider resolution goes through Registry.
10. DistributionAgent never imports concrete adapters.
11. MediaAgent never imports LechuangAdapter.
12. External actions require Publish Gate.
13. Provider capabilities require verification.
14. Generation respects credit budgets and idempotency keys.
15. Assets are immutable and keyed by sha256.
16. Async generation is worker-driven; agents do not sleep.
17. Judge never publishes.
18. ContentPackage is downstream of MediaAsset.
19. Successful external actions create Publication.
20. Publication IDs are never conflated.
21. Every external action is idempotent.
22. Analytics flows back into Memory, including workflow performance.
23. Memory flows into Strategy and workflow selection.
24. Commerce is decoupled from Content.
25. Secrets never enter source control.
26. Research never fabricates live data.
27. Unsupported or unverified APIs return BLOCKED, never a fake PASS.
28. No compatibility layer for deleted architecture.
29. Production nodes execute real work or BLOCKED.
30. PostgreSQL is metadata source of truth; files are bytes; memory is cache.
31. Runtime never auto-creates schema.
32. Workers take a database lease before resume.
33. DAG cycles, missing deps, and unknown nodes fail closed.
34. Workflow versions are immutable.
35. Node outputs store references, not copied domain objects.
36. Technical QA is local; AI Judge requires a vision provider.
37. ContentFitJudge is not ContentPolicyGate.
38. Creative code never imports distribution adapters.

Lechuang is a generation provider. Postiz is a distribution provider.
Meiti owns business intelligence, content, memory, strategy, commerce,
analytics, gates, and creative workflows.
