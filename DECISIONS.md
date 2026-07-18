# meiti DECISIONS

- **2026-07-18** 老板：`xiaoshuo` + `xiaoping` → **`meiti`**（并行双线、单一 owner）。
- Skills：meiti 根共享；不装 taste-skill/整仓 agency。
- 与 **xiaodian**：内容 meiti，商品 xiaodian；交接协议见 `docs/XIAODIAN_HANDOFF_PROTOCOL.md`。
- Obsidian：社交媒体+文案 → `Project/meiti`；神临同步。
- **DB**：5445 = meiti 根（pgvector + KG + gates + 统一审计）。5443/5444 子线历史保留，新向量不写子线库。
- **Embedding**：默认 `MEITI_EMBEDDING_PROVIDER=hash` 可离线验证；生产可切 openai。
- **Gate**：DB `publish_gates` + CLI；默认 locked；approve 仅 boss/owner/老板。
- **CDP**：新增 `meiti` 9339；历史 xiaoping/xiaoshuo 端口保留；提供 meiti-* 别名。
- 记忆分层：代码图谱 ≠ 内容向量/KG ≠ AgentMemory ≠ Obsidian。
