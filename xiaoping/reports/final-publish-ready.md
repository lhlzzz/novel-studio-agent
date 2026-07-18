# xiaoping 首批无第三方水印样片清单

更新时间：2026-06-15 00:14 +0800

> 本文件替代此前“最终发布就绪”口径。当前仅表示首批无第三方水印样片已生成并通过本地技术验证，不表示已获真实发布批准。

## 当前有效视频清单

| 序号 | 文件 | 内容方向 | 生成方式 | 状态 |
|---|---|---|---|---|
| 01 | `videos/publish-ready/01-youtube-shorts-ai-script-prompt.mp4` | AI 脚本工具：三行信息生成可改脚本骨架 | Remotion | ✅ 可审 |
| 02 | `videos/publish-ready/02-xiaohongshu-customer-reply-prompt.mp4` | 客服回复草稿：AI 只写草稿，真人审核 | Remotion | ✅ 可审 |
| 03 | `videos/publish-ready/03-bilibili-quote-draft-prompt.mp4` | 商品信息草稿：报价前先整理待确认字段 | Remotion | ✅ 可审 |

## 无效旧资产处理

此前 10 平台/26+ 文件批量清单已经失效：这些文件多数来自 Pixelle 水印素材或错误复制链路，已从 `videos/publish-ready/` 移出。

- 旧 publish-ready 归档：`videos/rejected-watermarked/2026-06-14-publish-ready/`
- 旧 Pixelle/MPT 输出归档：`videos/rejected-watermarked/2026-06-14-output/`

## 技术验证

- `remotion compositions`：通过，6 个 composition 可列出。
- `remotion render`：3 条当前样片渲染完成。
- `ffprobe`：三条均为 720x1280、24fps、约 43.1s。
- `ffmpeg -f null -`：三条均完整解码无错误。
- 抽帧复核：`videos/output/no-watermark-check-01.png`、`02.png`、`03.png` 未见 Pixelle 第三方水印。

## 发布前内部检查

- [ ] 老板确认要保留的内容方向。
- [ ] 针对目标平台重写标题、封面文案、标签。
- [ ] 检查是否仍有“收益承诺、成交承诺、自动触达、真实报价”等风险表达。
- [ ] 确认素材/字体/模板来源可复核。
- [ ] 获得真实发布批准后，由人工执行发布。

## 边界

- 当前不执行真实发布、私信、评论、报价、收款、上架、订单处理或账号自动化。
- 不再使用强制水印 Pixelle 输出作为成片。
