# xiaoping 发布前内部汇总报告

更新时间：2026-06-15 00:14 +0800

## 当前阶段

**状态**：已从“Pixelle 水印占位资产误入 publish-ready”回退并修复为“3 条 Remotion 无第三方水印内部审片样片”。

> 这不是发布批准。B 模式下仍只允许研究、审片、样片验证、内容结构验证、数据记录和内容层 ROI 研究。

## 本轮完成

- 已停止把原 `videos/publish-ready/` 的 Pixelle / MoneyPrinterTurbo 派生文件当成发布资产。
- 已把 27 个旧 `publish-ready` MP4 归档到 `videos/rejected-watermarked/2026-06-14-publish-ready/`。
- 已把 5 个 Pixelle / MPT 派生输出归档到 `videos/rejected-watermarked/2026-06-14-output/`。
- 已将 MoneyPrinterTurbo 活跃本地素材目录中的 `pixelle-static-smoke.mp4` 移出，避免后续误用强制水印素材。
- 已用现有 Remotion 工程重渲染 3 条无第三方水印样片。
- 已同步更新 `videos/output/` 中对应 Remotion 输出副本。

## 当前可审样片

| 序号 | 平台用途 | 文件 | 主题 | 时长 | 验证 |
|---|---|---|---|---:|---|
| 01 | YouTube Shorts / 短视频通用 | `videos/publish-ready/01-youtube-shorts-ai-script-prompt.mp4` | AI 脚本工具 | 43.1s | ffprobe + ffmpeg 解码 + 抽帧 |
| 02 | 小红书 / 图文口播通用 | `videos/publish-ready/02-xiaohongshu-customer-reply-prompt.mp4` | 客服回复草稿 | 43.1s | ffprobe + ffmpeg 解码 + 抽帧 |
| 03 | B站 / 知识向通用 | `videos/publish-ready/03-bilibili-quote-draft-prompt.mp4` | 商品信息草稿 | 43.1s | ffprobe + ffmpeg 解码 + 抽帧 |

## 验证结果

- 三条新视频均为 720x1280、24fps、约 43.1 秒。
- 三条新视频均可完整解码，`ffmpeg -v error -i <file> -f null -` 无错误输出。
- 抽帧文件：
  - `videos/output/no-watermark-check-01.png`
  - `videos/output/no-watermark-check-02.png`
  - `videos/output/no-watermark-check-03.png`
- 抽帧画面未见 `Pixelle-Video` 第三方水印。

## 当前边界

### 可继续做
- 继续内部审片、标题/封面/标签草案、平台规则证据补充。
- 继续用 Remotion / ffmpeg 生成原创图文动效样片。
- 使用 MoneyPrinterTurbo 前必须确认输入素材不带第三方水印，且输出逐条抽帧复核。

### 不再做
- 不再使用 Pixelle-Video 强制水印输出作为视频成片或 MPT 本地素材。
- 不再运行 `/tmp/batch_generate.py` / `/tmp/batch_generate_v2.py` 这类“取最近任务目录再复制”的错误链路。
- 不再把带水印或内容不匹配文件放入 `videos/publish-ready/`。

### 仍需批准
- 真实账号注册、登录、发布。
- 私信、评论运营、报价、收款、商品/订单、投流、直播。

## 下一步

1. 老板先看 3 条无第三方水印样片，决定保留哪条方向。
2. 若要做平台发布候选，再按目标平台重新定标题、封面、标签和结尾 CTA。
3. 发布动作仍需单独批准并人工执行。
