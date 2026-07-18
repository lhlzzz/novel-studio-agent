# xiaoshuo — 网文写作工具集

## Skill 路由表

| 命令 | Skill | 说明 |
|------|-------|------|
| `/story-long-write`、`/写长篇` | story-long-write | 长篇网文写作（逐章推进） |
| `/story-short-write`、`/写短篇` | story-short-write | 短篇网文写作（情绪驱动） |
| `/story-long-analyze`、`/长篇拆文` | story-long-analyze | 长篇小说深度拆解 |
| `/story-short-analyze`、`/短篇拆文` | story-short-analyze | 短篇小说拆文分析 |
| `/story-long-scan`、`/长篇扫描` | story-long-scan | 长篇小说批量扫描 |
| `/story-short-scan`、`/短篇扫描` | story-short-scan | 短篇小说批量扫描 |
| `/story-deslop`、`/去AI味` | story-deslop | 去除 AI 写作痕迹 |
| `/story-cover`、`/封面` | story-cover | 生成封面图 |
| `/story-review`、`/审查` | story-review | 多视角对抗式审查 |
| `/story-import`、`/导入` | story-import | 逆向导入已有小说到项目结构 |
| `/story`、`/网文` | story | 工具箱路由 · 模糊意图自动分发 |
| `/story-setup`、`/准备写书` | story-setup | 环境部署 · hooks/rules/agents 一键部署 |
| `/browser-cdp` | browser-cdp | 浏览器 CDP 工具 |

## 文件结构

- `拆文库/` — 拆文分析结果存放目录
- `我欠三百万，修bug续命/正文/` — 长篇小说正文章节
- `我欠三百万，修bug续命/设定/` — 角色设定、世界设定
- `我欠三百万，修bug续命/大纲/` — 卷纲、细纲
- `我欠三百万，修bug续命/追踪/` — 上下文.md（写作上下文）、伏笔.md
- `我欠三百万，修bug续命/对标/` — 对标作品分析

## 协作规则

Agent 间的协调关系由各 Agent 定义文件的职责边界描述，不需要独立协调规则文件。

## Compact 后恢复上下文

此部分在 compact 后自动生效。CLAUDE.md 在每次 compact 后会被重新加载。
写作中的关键上下文：
1. 当前写作项目名称和进度
2. 最近讨论的角色设定变更
3. 未完成的伏笔列表
4. 当前章节的情绪/节奏目标

如果存在 我欠三百万，修bug续命/追踪/上下文.md，compact 后首先读取恢复上下文。

## Agent skills

### Issue tracker

Issues and PRDs are tracked as local markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default Matt Pocock five-label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

Use a single-context layout: root `CONTEXT.md` and `docs/adr/` when present. See `docs/agents/domain.md`.

## 固定工具链

- 代码结构、符号、调用链、影响面优先使用 codebase-memory-mcp（`index_repository`、`search_graph`、`trace_path`、`get_code_snippet`、`query_graph`、`search_code`）；未索引时先索引当前 workspace，再按需回退 CodeGraph/GitNexus/grep。
- 进入本 workspace 后先读根级 `/root/hermes/company-ai-system/CLAUDE.md`、本目录 `TOOLING.md`，外部工具统一走 `/root/hermes/company-ai-system/tools/external/TOOLING.md`。
- 小说/长内容任务优先使用 story skills/agents；代码类任务再用 CodeGraph、GitNexus 和 Karpathy。
- 代码结构、符号、调用链、文件定位优先用 CodeGraph；索引过期或为空时在本 workspace 运行 `codegraph sync`，不要重装工具。
- API、流程、跨模块影响面、当前 diff 风险用 GitNexus。
- 写代码、重构、review 前调用 `andrej-karpathy-skills:karpathy-guidelines`，保持最小改动和明确验证标准。
- 跨会话偏好、项目事实和非代码经验用 AgentMemory/现有记忆系统；不要把代码或 git 可推导信息写入长期记忆。
- 本项目专业工具固定使用 story 工具链、ComfyUI 工作流参考、MediaCrawler 公开舆情候选和项目隔离浏览器 MCP。

## 数据库模块

- 本项目持久化入口固定为 `scripts/db/`：`engine.py` 负责连接与会话，`models.py` 负责 ORM 表，`migrate.py` 负责初始化与状态检查。
- 默认使用 PostgreSQL + SQLAlchemy；连接串优先读取 `DATABASE_URL`，未设置时使用 `postgresql://xiaoshuo:xiaoshuo@localhost:5443/xiaoshuo`。
- 初始化/检查/自举命令：`python scripts/db/migrate.py init`、`status`、`seed`、`verify`、`report`、`bootstrap`。
- 智能体系统级基础表由 `scripts/db/models.py` 统一拥有：`agent_runs`、`agent_tasks`、`agent_decisions`、`agent_artifacts`、`agent_metrics`、`agent_records`。
- 本地开箱即用优先走 `docker compose -f docker-compose.db.yml up -d`（或 `docker-compose -f docker-compose.db.yml up -d`）+ `cp .env.example .env`；新开发者应先跑 `python scripts/db/migrate.py bootstrap`，随后执行 `python scripts/db/migrate.py report` 做只读检查。
- 新增持久化需求时优先扩展 `scripts/db/models.py`，不要散落 JSONL/临时文件，也不要新增第二套数据库 helper。

## Workspace 整理边界

- 开工必读：`TASK.md`、`STATE.md`、`SESSION.md`、`NEXT_ACTION.md`、`HANDOFF.md`、`DECISIONS.md`、`RULES.md`、`TOOLING.md`，写作中还要读 `我欠三百万，修bug续命/追踪/上下文.md`（如存在）。
- 保留证据：正文章节、设定/大纲/追踪、拆文和审稿资料、deliverables、发布/备份包、`novel_runtime_recheck.json`、研究文档和封面/素材证据。
- 本地噪音：`.codegraph/`、`.gitnexus/`、`.rtk/`、浏览器 profile、临时缓存和自动化工具状态只通过 ignore 隔离，不删除写作资产。
- 验证入口：优先使用 story scan/review、章节连续性复核、发布候选检查和根级 `scripts/scheduler.sh`；涉及持久化改动时优先跑 `python scripts/db/migrate.py bootstrap`，单独排障时再用 `status` / `seed` / `verify` / `report`。

## Claude 模型池落地

本项目按具体工作项定档，不按 Hermes 旧 agent 身份、xiaochan 或 light routing 配置定档；Claude/Codex 也不是固定分工，谁执行都先按工作项选模型。

- Haiku（`claude-haiku-4-5`）：只做低成本、可逆、偏读的工作：读 `TASK/STATE/SESSION/NEXT_ACTION/HANDOFF/LOG`、找路径、扫目录、提取事实、机械更新日志/状态。不能做架构判断、代码方案、风险裁决，也不要把上下文摘要升级成决策。
- Sonnet（`claude-sonnet-4-6`）：默认例行执行档：跑命令/测试、整理失败证据、收集公开网页/浏览器证据、按已确认目标做小而明确的改动、把已有证据整理成资料包。若根因不明、影响面不清、多文件联动或证据冲突，停止并升级。
- Opus（`claude-opus-4-7`）：用于架构理解、方案选择、代码编写/重构、非显然 bug、复杂调试、跨文件一致性、风险审查、最终审查，以及任何外部可见或不可逆动作。

Agent 工具限制：不要把 Haiku 用作 Agent/Explore 子代理模型；Agent 的 `haiku` 或默认 Explore 会映射到不可用的带日期 Haiku。调用 Explore 或只读自定义子代理时显式使用 Sonnet（`model: "sonnet"`）；若确需 Haiku，只通过 `claude -p --model claude-haiku-4-5` 或主会话路由使用。

升级规则：低档发现不确定、冲突、跨项目/跨 workspace 影响，或涉及生产、安全、资金、支付、发布、法务、税务、交易/实盘风险时，先升 Opus 再判断或落地。代码落地后，纯状态整理可降回 Haiku/Sonnet；最终风险判断仍回 Opus。

## Context Policy

按 Claude Code 当前 context 使用量执行：

- 0–40%：正常执行。
- 40–60%：更新状态文件。
- 60–70%：生成 handoff。
- 70%+：优先保存状态、执行 `/clear`、开启新 session。

除非绝对必要，避免反复 `/compact`。

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (60-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk go test             # Go test failures only (90%)
rtk jest                # Jest failures only (99.5%)
rtk vitest              # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk pytest              # Python test failures only (90%)
rtk rake test           # Ruby test failures only (90%)
rtk rspec               # RSpec test failures only (60%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%). Format flags (-c, -l, -L, -o, -Z) run raw.
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **xiaoshuo** (2983 symbols, 2966 relationships, 0 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/xiaoshuo/context` | Codebase overview, check index freshness |
| `gitnexus://repo/xiaoshuo/clusters` | All functional areas |
| `gitnexus://repo/xiaoshuo/processes` | All execution flows |
| `gitnexus://repo/xiaoshuo/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
