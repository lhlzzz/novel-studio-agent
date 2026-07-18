# xiaoping 全平台视频资产状态

更新时间：2026-06-15 00:14 +0800

> 本文件不再记录“15 平台全部发布就绪”。此前全平台批量 MP4 已确认包含 Pixelle 水印/占位素材误归档问题，当前已从活跃发布目录移出。

## 当前结论

- `videos/publish-ready/` 当前只保留 3 条无第三方水印 Remotion 样片。
- 原 27 个 publish-ready MP4 已归档到 `videos/rejected-watermarked/2026-06-14-publish-ready/`，不得再作为发布资产引用。
- 原 5 个 Pixelle/MoneyPrinterTurbo 派生输出已归档到 `videos/rejected-watermarked/2026-06-14-output/`。
- 全平台扩展要重新从无水印素材链路开始，不沿用 `/tmp/batch_generate.py` 或 `/tmp/batch_generate_v2.py`。

## 当前活跃 publish-ready 目录

```text
workspaces/xiaoping/videos/publish-ready/
├── 01-youtube-shorts-ai-script-prompt.mp4
├── 02-xiaohongshu-customer-reply-prompt.mp4
└── 03-bilibili-quote-draft-prompt.mp4
```

## 平台覆盖状态

| 平台组 | 当前状态 | 下一步 |
|---|---|---|
| YouTube Shorts / 海外短视频 | 只有 1 条无水印通用样片 | 需要英文字幕/标题/封面二次适配 |
| 小红书 / 视频号 | 只有 1 条客服回复草稿样片可审 | 需要平台规则和发布前文案二次适配 |
| B站 / 知识向 | 只有 1 条商品信息草稿样片可审 | 可扩成知识向版本，但仍需人工复核 |
| 抖音、快手、知乎、微博、TikTok、Instagram、LinkedIn、Reddit、Pinterest | 旧批量资产已失效 | 需要重新生成，且每条必须先过无水印抽帧验证 |

## 后续全平台生成规则

1. 先确认素材源无第三方水印；强制水印工具产物不得进入成片链路。
2. 每次生成后只接受“当前命令真实产物路径”，不得取最近任务目录复制。
3. 每条进入 `publish-ready/` 前必须通过：
   - `ffprobe` 规格检查；
   - `ffmpeg -v error -i <file> -f null -` 完整解码；
   - 抽帧人工复核，无 Pixelle/模板站/第三方水印；
   - 文件名、内容主题、平台用途一致性检查。
4. 真实发布仍需老板单独批准并人工执行。
