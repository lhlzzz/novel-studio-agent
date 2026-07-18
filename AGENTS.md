# meiti — 媒体部（合并入口）

> 身份：`Meiti-MediaCore`  
> 由 **xiaoping（分发/变现）** + **xiaoshuo（长内容/叙事）** 合并；顶层不再并列 `xiaoshuo` / `xiaoping` 为独立 workspace。

## 职责边界

1. **主目标是盈利**（真实或可验证的现金流路径设计），不是纯曝光或纯写稿。
2. 覆盖 **国内 + 海外** 主流社交与内容平台：小红书、视频号、抖音、快手、公众号、微博、B 站、知乎、闲鱼、TikTok、X、YouTube Shorts、IG Reels、Threads 等。
3. **内容形态**：
   - P0：推文（图+文+音）— 默认在 `xiaoping/`
   - P0b：长内容/网文（大纲→正文→质量门）— 默认在 `xiaoshuo/`
   - P1：短视频衍生（从推文核或章节核改编）
4. **与 xiaodian**：meiti 出内容包、钩子、listing 文案侧；xiaodian 出 SKU/供应/履约。共用盈利叙事，不各写一套。
5. **外部动作 gate**：真实登录、发布、私信、上架、报价、收款、投流 → 必须老板明确批准。
6. 不切换其他 workspace 作为主执行面；允许为对接 xiaodian 读写其状态文档。

## 并行模型（不是串行闸门）

- `xiaoping/` 与 `xiaoshuo/` 是 **并行能力线**，不是必须先写完小说才能做推文。
- 嵌套在 `meiti/` 下 = **单一对外 owner / 单一入口**，不是把两边拆成两个无关 workspace，也不是强制流水线排队。
- 两边可同时推进；联动任务（章节→推文、推文→长文）在本目录协调，最小改两边。

## 子目录路由

| 意图 | 进入 | 说明 |
|------|------|------|
| 推文包 / 出海 / 变现实验 / 平台规则 | `xiaoping/` | 先读该目录 `RULES.md` + `karpathy-guidelines` |
| 网文写作 / 拆文 / 去 AI 味 / 封面 | `xiaoshuo/` | 走 story-* skills |
| 营销/社媒写作 skill | 本目录 `.claude/skills/` | 两边共享，见 `SKILLS_INDEX.md` |
| 两边联动 | 本目录协调 + 两边最小改动 | 不复制第三套流水线 |

## 强制启动清单

1. 读 `RULES.md`、`STATE.md`、`NEXT_ACTION.md`
2. 任务落在哪一边，就加载该子目录约束（xiaoping 必加载 `karpathy-guidelines`）
3. 声明 `GOAL` + `VERIFY` 后再改文件
4. 结构检索优先 codebase-memory-mcp（索引 `meiti` 根或具体子目录）
5. 公开网页：CloakBrowser + Scrapy；禁止自动过人机

## 模型定档

与子目录一致：Haiku 只读整理；Sonnet 例行执行；Opus 架构/风险/发布相关。

## Context Policy

0–40% 正常；40–60% 更新状态；60–70% handoff；70%+ 保存后 `/clear`。
