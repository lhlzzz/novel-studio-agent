---
title: MeitiAgent 工作区知识图
owner: Meiti-MediaCore
type: knowledge-graph
version: 2.0
---

# MeitiAgent 工作区知识图

## Nodes

- **Agent**: Meiti-MediaCore
- **Shared Runtime**: `scripts/`
- **Approval Owner**: `.gates/` + `publish_gates`
- **Architecture**: Platform is an integration, never an agent or workspace.
- `agents/` owns capability agents; `integrations/` owns provider adapters.
- **Knowledge Graph**: `.understand-anything/knowledge-graph.json`

## Relationships

- `packages/` 和 `evidence/` 由 Meiti 管理，内容与分发通过独立契约关联。
- `scripts/publish_gate.py` 负责审批检查，不执行真实发布。
- `gpt-image-2-style-library` 通过 `media-agent` 提供共享媒体能力。

## Last Updated

2026-08-25

## Analysis Record

- UnderstandAnything 扫描 247 个文件，生成中文图谱：256 个节点、262 条关系、9 个架构层。
- 图谱完整性校验通过：247 个扫描文件均有且仅有一个文件节点与一个架构层归属。
- `python -m pytest` 验证共享 Meiti 契约。
- `scripts/db/migrate.py status`：本机 127.0.0.1:5445 PostgreSQL 连接被拒绝。
- 已安装上游 `freestylefly/awesome-gpt-image-2` 的 `gpt-image-2-style-library`，固定 commit `685469889fb72fd5adefae45e1645d527edcb5e7`。
- 媒体 skills、API client、密钥和生成资产仍由 Meiti 统一管理。
