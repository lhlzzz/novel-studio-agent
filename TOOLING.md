# meiti TOOLING

共享外部工具入口：`/root/hermes/company-ai-system/tools/external/TOOLING.md`

## 子目录工具真相源

| 区域 | 入口 |
|------|------|
| 分发/变现 | `xiaoping/TOOLING.md`、`xiaoping/SKILLS_INDEX.md` |
| 长内容 | `xiaoshuo/TOOLING.md`、story-* skills（全局 `/story` 路由） |

## 统一数据库（PostgreSQL + pgvector · 5445）

| 项 | 值 |
|----|-----|
| Compose（Docker 路径） | `meiti/docker-compose.db.yml` → `pgvector/pgvector:pg16` |
| 本机现状 | native PG14 cluster `meiti` **:5445** + pgvector **0.8.0**（源码安装） |
| DB / user | `meiti` / `meiti` |
| URL | `postgresql://meiti:meiti@127.0.0.1:5445/meiti` |
| Env | `.env`（见 `.env.example`） |
| 职责文档 | [`docs/DB_OWNERSHIP.md`](docs/DB_OWNERSHIP.md) |

表：`agent_*` + `content_embeddings` + `content_entities` + `content_relations` + `publish_gates`

```bash
cd /workspace/hermes-workspaces/meiti
# Docker 可用时：
# docker compose -f docker-compose.db.yml up -d

python scripts/db/migrate.py bootstrap
python scripts/db/migrate.py status
python scripts/db/migrate.py report
```

子线历史库（可选、暂保留）：xiaoshuo **5443** / xiaoping **5444**。新内容向量与 gate **只认 5445**。

## Embedding 管线

```bash
# 默认本地 hash 向量（无外网 API）
export MEITI_EMBEDDING_PROVIDER=hash
python scripts/embeddings.py selftest
python scripts/embeddings.py ingest --file path/to.md --key-prefix mydoc --source-line xiaoping
python scripts/embeddings.py search "查询句" --limit 5

# 可选真实 embedding
# export MEITI_EMBEDDING_PROVIDER=openai OPENAI_API_KEY=...
```

## 内容知识图谱

```bash
python scripts/content_kg.py seed-package --package-key tweet-package-01-ai-efficiency-profit
python scripts/content_kg.py neighbors --key tweet-package-01-ai-efficiency-profit
python scripts/content_kg.py list-entities --type platform
```

## Publish gate（永不自动发布）

```bash
python scripts/publish_gate.py selftest
python scripts/publish_gate.py request --action publish --platform xiaohongshu \
  --package-key tweet-package-01-ai-efficiency-profit \
  --package packages/tweet-package-01-ai-efficiency-profit.md
python scripts/publish_gate.py check --package-key tweet-package-01-ai-efficiency-profit
# 仅老板：approve --by boss
```

见 [`.gates/publish.md`](.gates/publish.md)。

## 常用验证

```bash
python meiti/xiaoping/self_media_profit_agent.py selftest
python meiti/xiaoshuo/scripts/novel_demo.py
python meiti/scripts/db/migrate.py verify
python scripts/agent_db_smoke.py --project meiti --skip-bootstrap   # from repo root
```

## CDP

```bash
hermes-cdp meiti --dry-run          # port 9339, profile meiti
hermes-cdp meiti-xiaoping --dry-run # alias → xiaoping 9336
hermes-cdp meiti-xiaoshuo --dry-run # alias → xiaoshuo 9335
# 历史名仍可用：hermes-cdp xiaoping / xiaoshuo
```

## 采集

- CloakBrowser + Scrapy（规则同 xiaoping）
- 禁止自动过人机

## 共享 skills + context

```bash
ls meiti/.agents/skills
ls meiti/.agents/product-marketing.md
ls meiti/.agents/social-media-context-sms.md
```

用 skill 前先 GOAL/VERIFY；**输出≠发布**。

## xiaodian 交接

- 协议：[`docs/XIAODIAN_HANDOFF_PROTOCOL.md`](docs/XIAODIAN_HANDOFF_PROTOCOL.md)
- 实例：`packages/tweet-package-01-ai-efficiency-profit.handoff.json`

## Obsidian

- Project：`D:\obisidian\Obsidian\Project\meiti`
- 神临：`D:\obisidian\Obsidian\神临` → `项目接口/meiti.md`
