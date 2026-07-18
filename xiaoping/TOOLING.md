# xiaoping TOOLING

共享工具入口：`/root/hermes/company-ai-system/tools/external/TOOLING.md`

## 内容形态优先级

1. **推文主路（当前）**：多图 + 文案 + 音频/TTS，小红书式；一稿多平台适配。
2. **出海润色**：国内主稿 → TikTok / X / IG / YT 本地化（先英文化，再按市场扩展）。
3. **静态图文备选**：Pixelle-Video 静态页 / 图片封装。
4. **短视频衍生**：Remotion 程序化字幕/图文动画；`ffmpeg`/`ffprobe` 检查。

## 网页采集（老板指定主链路）

| 工具 | 用途 | 仓库 |
|------|------|------|
| **CloakBrowser** | 稳定 Chromium / 反检测浏览、公开页渲染、与 Playwright API 兼容采集 | https://github.com/CloakHQ/CloakBrowser |
| **Scrapy** | 批量公开页爬取、管道清洗、结构化落盘 | https://github.com/scrapy/scrapy |

### 本机状态（2026-07-17 核验）

- `cloakbrowser info`：已安装（chromium 可用）
- `scrapy version`：Scrapy 2.16.0 可用
- 项目浏览器 MCP 仍可用作补充：`playwright-xiaoping` / CDP `9336`

### 使用规则

- 默认研究流：CloakBrowser 打开/渲染 → 需要批量时用 Scrapy 抽字段。
- 只采集**授权范围或公开可访问**页面；结果写入 `RESEARCH.md` 或 `reports/`，带来源。
- **禁止**自动绕过验证码、滑块、短信、人脸；**禁止**破坏性爬取与未授权登录。
- 不要把 CloakBrowser/Scrapy 源码 repo clone 进本 workspace；需要实验放共享 `tools/external/labs/`。
- 爬取内容仅供内部研究；发布素材必须原创改写。

### 最小命令备忘

```bash
cloakbrowser info
scrapy version
# 具体 spider 按任务在共享 labs 或临时目录创建，不污染 workspace 根
```

## 代码与技能索引

| 工具 | 用途 | 仓库 / 入口 |
|------|------|-------------|
| **codebase-memory-mcp** | 符号/调用链/结构检索，降低 grep 成本 | https://github.com/DeusData/codebase-memory-mcp |
| MCP 调用 | `index_repository` / `search_graph` / `search_code` / `trace_path` / `query_graph` | MCP server: `codebase-memory-mcp` |
| Karpathy 约束技能 | 每次任务启动加载 | `.claude/skills/karpathy-guidelines/SKILL.md` |
| 上游参考 | Claude 用 Karpathy 指南 | https://github.com/multica-ai/andrej-karpathy-skills |

### 索引约定

- 进入本 workspace 后若结构检索变慢或未索引：对 `/workspace/hermes-workspaces/xiaoping` 跑 `index_repository`（mode 建议 `moderate` 或 `fast`）。
- 技能与文档变更后可再索引，便于 `search_code` 命中 `SKILL.md` / `RULES.md`。
- 索引不能替代源码与 git diff 作为最终真相。

## 其他可用工具

- Remotion 源码：`/root/hermes/company-ai-system/tools/external/repos/remotion`
- Remotion CLI：`/root/hermes/company-ai-system/tools/external/bin/node-tool remotion --help`
- Pixelle-Video 源码：`/root/hermes/company-ai-system/tools/external/repos/Pixelle-Video`
- Pixelle-Video 运行方式：`uv --directory /root/hermes/company-ai-system/tools/external/repos/Pixelle-Video run ...`
- `ffmpeg` / `ffprobe`：音视频与导出检查
- MediaCrawler：`/root/hermes/company-ai-system/tools/external/bin/mediacrawler --help`（仅授权/公开舆情候选）

## 使用规则（内容生产）

- 默认先产出推文素材包（图清单、正文、音频稿、平台差异表、出海润色栏），再按需要衍生短视频。
- Remotion 用于程序化短视频、批量模板、字幕/图文动画、脚本到视频原型。
- Pixelle-Video 当前只验证到静态模板/图片页 + Edge TTS 可封装 MP4；按历史反馈暂不作为主视频产品线。
- 不要把 `node_modules`、Python venv 或外部 repo 装进本 workspace。
- 任意平台真实账号发布、素材版权、商业承诺和平台合规仍需老板明确批准。
- 使用结果写入 `RESEARCH.md` 或 `SESSION.md`。

## 通用浏览器 / profile

- 当前项目浏览器 MCP：`playwright-xiaoping` / `chrome-devtools-xiaoping`。
- 当前项目浏览器 profile：`/root/.claude/browser-profiles/xiaoping/`。
- 当前项目浏览器输出：`/root/.claude/browser-output/xiaoping/`。
- 固定 CDP 端口：`9336`；启动：`hermes-cdp xiaoping`；连接：`agent-browser --cdp 9336 ...`。
- 遇到验证码、滑块、短信、人脸或其他人机验证时，停止自动化并请求用户手动处理。
