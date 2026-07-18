# meiti HANDOFF

## 完成（2026-07-18 补齐轮）

| 项 | 状态 |
|----|------|
| Obsidian meiti + 神临 | 完成 |
| PG+pgvector 5445 运行时 | 完成（native cluster） |
| Embedding ingest/search | 完成（hash；推文包已入库） |
| Content KG schema+seed | 完成 |
| Publish gate CLI | 完成（包=requested，未批准） |
| 首包+证据+handoff | 完成 |
| xiaodian 协议 | 完成 |
| 三库职责文档 | 完成 |
| CDP meiti 身份 | 完成（9339 + 别名） |
| dashboard/smoke | 完成（含 meiti） |
| product/social context | 完成 |

## 验证命令（已跑通）

```bash
cd meiti
python scripts/db/migrate.py verify
python scripts/embeddings.py selftest
python scripts/content_kg.py seed-package --package-key tweet-package-01-ai-efficiency-profit
python scripts/publish_gate.py selftest
python scripts/publish_gate.py check --package-key tweet-package-01-ai-efficiency-profit  # exit 1 expected
python ../scripts/agent_db_smoke.py --project meiti --skip-bootstrap
hermes-cdp meiti --dry-run
```

## 下一步（仅剩业务/人工）

1. 老板是否 `approve` 发布 gate（当前不应自动批）。
2. xiaodian 填 `NEED_EVIDENCE`（交付/类目/底价）。
3. 真图/真 TTS 资产（禁止伪造截图当证据）。
4. 可选：`MEITI_EMBEDDING_PROVIDER=openai` 换真向量。
5. 长内容线第 011 章等（见 xiaoshuo NEXT_ACTION）。

## 风险

- skill「发布」话术仍受 gate 约束。
- hash 向量只适合结构验证，不适合生产语义检索质量。
- Docker compose 路径保留；当前运行时是 native 5445。
