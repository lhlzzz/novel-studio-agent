# meiti STATE

- **2026-07-18**：新建 `meiti/`；`xiaoshuo` ∥ `xiaoping` 并行嵌入。
- Skills：marketingskills×4、social-media-skills×9、impeccable×1。
- Obsidian：`Project/meiti` 合并社交媒体+文案；神临已同步。
- **DB 5445 已运行时验证**：native PG14 cluster + pgvector 0.8.0；`migrate.py bootstrap` OK。  
  表：agent_* + content_embeddings + content_entities + content_relations + publish_gates。
- **Embedding 管线**：`scripts/embeddings.py`（hash 默认；可切 openai）；已 ingest 推文包 9 chunks + selftest。
- **内容 KG**：`scripts/content_kg.py`；tweet-package-01 图谱已 seed。
- **Publish gate**：`scripts/publish_gate.py` + `.gates/publish.md`；包 gate 状态 `requested`（未批准 → check 拒绝）。
- **首包**：`packages/tweet-package-01-*` + `evidence/tweet-package-01/` + xiaodian handoff JSON。
- **三库职责**：`docs/DB_OWNERSHIP.md`（5445 主；5443/5444 历史保留）。
- **CDP**：`hermes-cdp meiti` → 9339；`meiti-xiaoping`/`meiti-xiaoshuo` 别名保留子线。
- **dashboard/smoke**：含 `meiti` + 端口映射 5445。
- **Context**：`.agents/product-marketing.md`、`.agents/social-media-context-sms.md`。

## 子状态入口

- 分发/变现：`xiaoping/STATE.md`、`xiaoping/NEXT_ACTION.md`
- 长内容：`xiaoshuo/STATE.md`、`xiaoshuo/NEXT_ACTION.md`

## Portfolio DB (2026-07-18)

- 五库独立端口 SSOT：`docs/DB_OWNERSHIP.md` + `scripts/agent_db_smoke.py`
- meiti 仍为 **5445** 主写；不与 xiaogu/xiaomei/xiaodian/xiaodou 混库
- 向量只在本库 `content_embeddings`；不做 portfolio 全文镜像
