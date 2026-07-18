# xiaoshuo TOOLING

共享工具入口：`/root/hermes/company-ai-system/tools/external/TOOLING.md`

## 可用工具

- ComfyUI 源码：`/root/hermes/company-ai-system/tools/external/repos/ComfyUI`
- ComfyUI 命令：`/root/hermes/company-ai-system/tools/external/bin/comfyui`

## Smoke

```bash
/root/hermes/company-ai-system/tools/external/bin/comfyui --quick-test-for-ci --cpu --disable-api-nodes --dont-print-server
```

## 使用规则

- 用于封面、角色概念图、场景图、视觉 moodboard、封面工作流参考。
- 当前未下载模型，不做真实生图。
- 发布候选素材必须核对模型来源、素材版权、平台封面规范，并按平台/版权相关规则走 xiaochan + xiaofa。
- 不要把模型、Python 依赖或外部 repo 装进本 workspace。
- 使用结果写入 `RESEARCH.md` 或 `SESSION.md`。

## 通用浏览器 / 评论资料工具

- 当前项目浏览器 MCP：`playwright-xiaoshuo` / `chrome-devtools-xiaoshuo`。
- 当前项目浏览器 profile：`/root/.claude/browser-profiles/xiaoshuo/`。
- 当前项目浏览器输出：`/root/.claude/browser-output/xiaoshuo/`。
- 固定 CDP 端口：`9335`；启动：`hermes-cdp xiaoshuo`；连接：`agent-browser --cdp 9335 ...`。
- MediaCrawler：`/root/hermes/company-ai-system/tools/external/bin/mediacrawler --help`，仅用于授权/公开范围内的评论、社媒讨论和舆情采集候选。
- CloakBrowser：`cloakbrowser info`，用于稳定浏览器自动化环境；不得用于自动绕过验证码、滑块、短信、人脸或其他平台人机验证。
- 遇到验证码、滑块、短信、人脸或其他人机验证时，停止自动化并请求用户手动处理；完成后可继续自动化，或改用平台允许的官方接口/导出。

