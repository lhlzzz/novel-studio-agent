# meiti 三库职责（5443 / 5444 / 5445）

## 裁决（2026-07-18）

| 端口 | 库 | Owner | 写什么 | 不写什么 |
|------|-----|-------|--------|----------|
| **5445** | `meiti` | **meiti 根（唯一内容向量 + 统一审计入口）** | `content_embeddings`、`content_entities`、`content_relations`、`publish_gates`、跨线 agent 审计 | 子线私有运行时细节（除非回写摘要） |
| **5444** | `xiaoping` | 分发/变现子线 | xiaoping agent_runs/tasks 等历史与子线工作流 | 不作为新内容向量主库 |
| **5443** | `xiaoshuo` | 长内容子线 | xiaoshuo agent 表 / 小说侧历史 | 不作为新内容向量主库 |

## 原则

1. **新内容检索默认 5445**。ingest / search / KG / gate 只认 meiti 根库。
2. **子线库暂保留**，避免打断既有 migrate/demo；**不强制迁移历史行**。
3. **禁止**再开第四个 meiti 相关 PG 端口。
4. Docker 路径：`meiti/docker-compose.db.yml` → 5445（`pgvector/pgvector:pg16`）。  
   本环境当前为 **native PG14 cluster `meiti` on 5445 + 源码安装 pgvector 0.8.0**。
5. agent_dashboard / agent_db_smoke：叶子名 + 端口映射见根 `scripts/`。

## 写入路由

```
推文包 / 平台适配 / 变现假设  → 可写 xiaoping 文件 + 摘要/向量进 5445
章节 / 拆文 / 长内容          → 可写 xiaoshuo 文件 + 摘要/向量进 5445
跨线决策 / gate / 交接协议    → 只写 5445 + meiti 根 docs
```
