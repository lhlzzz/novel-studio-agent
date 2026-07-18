# meiti — 媒体内容与增长变现

`meiti` 是 **xiaoshuo（长内容/叙事编纂）** 与 **xiaoping（全平台分发与变现）** 的合并体。  
工作区顶层只保留 `meiti`；历史资产以子目录嵌入：

| 子目录 | 原身份 | 职责 |
|--------|--------|------|
| [`xiaoping/`](xiaoping/README.md) | ContentCore | 推文包、多平台适配、出海润色、盈利实验、与 xiaodian 对接 |
| [`xiaoshuo/`](xiaoshuo/README.md) | Novel Studio | 网文/长内容：大纲、正文、拆文、去 AI 味、封面、审查 |

## 价值链（单一 owner）

```
选题/对标 → 长内容或推文核 → 多形态改编 → 视觉/音频
→ 平台适配（国内+海外）→ 发布前门禁 → 变现假设 → 复盘
     ↑ xiaoshuo                 ↑ xiaoping
```

- **主目标：盈利**（可验证现金流路径），不是纯曝光。
- **无老板 gate 不真实发布 / 不上架 / 不收款。**
- 商品/SKU/履约对接 **`xiaodian`**，meiti 不做虚构库存与底价。

## Demo

```bash
# 分发/变现侧
python meiti/xiaoping/self_media_profit_agent.py selftest

# 长内容侧
python meiti/xiaoshuo/scripts/novel_demo.py
```

## 进入本 workspace 时

1. 读本目录 `AGENTS.md`、`RULES.md`、`TOOLING.md`、`STATE.md`、`NEXT_ACTION.md`
2. 按任务进入 `xiaoping/` 或 `xiaoshuo/` 子目录执行（子目录保留各自 DB、skills、证据）
3. 跨两边任务以本目录为协调面，不在顶层再平行造第三套实现

## 并行说明

两边是 **并行子模块**（可同时推进），不是必须排队的流水线。  
放进 `meiti/` 只为：**对外一个入口、一套 RULES、共享 skills**。

## Skills

已装在 [`SKILLS_INDEX.md`](SKILLS_INDEX.md)（marketing + sms + impeccable）。

## 数据库（PostgreSQL + pgvector）

| 项 | 值 |
|----|-----|
| Port | **5445**（运行中 · native PG14 + pgvector） |
| Compose 备援 | [`docker-compose.db.yml`](docker-compose.db.yml) |
| 表 | agent_* · embeddings · content KG · publish_gates |
| 管线 | [`scripts/embeddings.py`](scripts/embeddings.py) · [`scripts/content_kg.py`](scripts/content_kg.py) · [`scripts/publish_gate.py`](scripts/publish_gate.py) |

```bash
python scripts/db/migrate.py bootstrap
python scripts/embeddings.py selftest
python scripts/publish_gate.py selftest
```

详见 [`TOOLING.md`](TOOLING.md)、[`docs/DB_OWNERSHIP.md`](docs/DB_OWNERSHIP.md)。

## 首包

- [`packages/tweet-package-01-ai-efficiency-profit.md`](packages/tweet-package-01-ai-efficiency-profit.md)
- 交接：[`docs/XIAODIAN_HANDOFF_PROTOCOL.md`](docs/XIAODIAN_HANDOFF_PROTOCOL.md)

## Obsidian

- 项目库：`D:\obisidian\Obsidian\Project\meiti`（合并原社交媒体 + 文案）
- 汇总：`D:\obisidian\Obsidian\神临` → `项目接口/meiti`
