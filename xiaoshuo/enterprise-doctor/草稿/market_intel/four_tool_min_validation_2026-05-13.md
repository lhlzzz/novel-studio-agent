# four_tool_min_validation_2026-05-13

## 1. 公开网页搜索/提取验证
- 工具：terminal/curl/Python urllib（web toolset 也已启用）
- 证据：`https://example.com` 返回 200，标题 `Example Domain`
- 结论：公开网页提取能力可用；严格市场研究时需记录 URL/标题/时间。

## 2. Chrome/浏览器验证
- 工具：Hermes browser toolset
- 证据 session_id：20260513_233059_b8bd52
- 验证内容：用 browser 打开 `https://example.com`，返回标题 `Example Domain` 与正文摘要。
- 结论：浏览器页面观察可用；不得绕登录/保存 cookie/token。

## 3. YouTube/视频字幕验证
- 工具：youtube-transcript-api 已安装且 import OK。
- 阻断：实时 fetch YouTube 示例视频超时，实际联网字幕抓取为 PARTIAL。
- 替代验证：使用本地字幕样例完成“字幕→结构分析→小说方法转化”。
- 证据：`market_intel/video_transcript_min_validation_2026-05-13.md`
- 结论：视频字幕分析流程可用；实时 YouTube 抓取需在网络稳定时复测。

## 4. GitHub 仓库理解验证
- 工具：git + read_file
- 证据仓库：`/root/hermes/company-ai-system/sandbox/github-trials/repos/llm-wiki-compiler`
- 已读文件：README.md
- 关键发现：llm-wiki-compiler 将 raw sources 编译成 interlinked markdown wiki；适合迁移为小说 wiki/hot/canon/foreshadowing 的长期知识沉淀流程。
- 结论：GitHub 仓库阅读和方法转技能可用。

## 5. Skill 写入验证
- 工具：skill_manage
- 目标 Skill：creative-market-research-toolchain
- 结论：见 skill_manage 创建结果。
