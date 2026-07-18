# xiaoping 发布前内部资料清单

更新时间：2026-06-15 00:14 +0800

> 当前仍处于 B 模式：以下视频仅供内部审片、老板预审和人工执行前准备，不构成发布批准。
>
> 已停止使用 Pixelle-Video / Pixelle 派生素材链路；强制水印或疑似水印来源不再进入 `videos/publish-ready/`。

## 当前无第三方水印核心视频样片

| 平台用途 | 文件名 | 规格 | 时长 | 生成链路 | 状态 |
|---|---|---:|---:|---|---|
| YouTube Shorts / 短视频通用 | `videos/publish-ready/01-youtube-shorts-ai-script-prompt.mp4` | 720x1280, 24fps | 43.1s | Remotion | ✅ 已重渲染、可解码、抽帧无 Pixelle 水印 |
| 小红书 / 图文口播通用 | `videos/publish-ready/02-xiaohongshu-customer-reply-prompt.mp4` | 720x1280, 24fps | 43.1s | Remotion | ✅ 已重渲染、可解码、抽帧无 Pixelle 水印 |
| B站 / 知识向通用 | `videos/publish-ready/03-bilibili-quote-draft-prompt.mp4` | 720x1280, 24fps | 43.1s | Remotion | ✅ 已重渲染、可解码、抽帧无 Pixelle 水印 |

## 已隔离的水印/无效资产

- 原 `videos/publish-ready/*.mp4` 共 27 个已移入：`videos/rejected-watermarked/2026-06-14-publish-ready/`。
- 原 Pixelle / MoneyPrinterTurbo 派生输出共 5 个已移入：`videos/rejected-watermarked/2026-06-14-output/`。
- MoneyPrinterTurbo 活跃本地素材目录已移除 `pixelle-static-smoke.mp4`，避免后续批量脚本再次误用强制水印素材。

## 三条样片内容定位

### 01 AI 脚本工具
- 内部标题候选：`不会写视频号脚本？先用三行信息拿到可改骨架`
- 适用平台：YouTube Shorts / 视频号 / B站 / 小红书均可二次适配。
- 人工检查重点：不承诺涨粉、成交或收入；不引导私信成交。

### 02 客服回复草稿
- 内部标题候选：`客服消息别让 AI 自动发：先写草稿再人工审核`
- 适用平台：小红书 / 视频号 / B站知识向。
- 人工检查重点：不得出现自动私信、自动回复、真实客户信息或订单信息。

### 03 商品信息草稿
- 内部标题候选：`报价单先别写价格：先整理商品信息草稿`
- 适用平台：B站 / 视频号 / 小红书知识向。
- 人工检查重点：单价、库存、交期、适配范围全部必须人工确认；不报价、不收款、不上架。

## 发布前检查项

### 内容合规检查
- [ ] 视频内容不包含虚假宣传、收益承诺。
- [ ] 不包含“稳赚”“包赚”“保证成交”等违规表达。
- [ ] 不包含 Pixelle-Video、第三方模板站或不可授权素材水印。
- [ ] 不包含搬运、二改他人内容。

### 账号与动作边界
- [ ] 确认账号为自创/自有/授权账号。
- [ ] 确认平台规则、发布资格和素材授权。
- [ ] 真实注册、登录、发布、私信、评论、报价、收款、投流、商品/订单动作均需老板明确批准。

## 数据监控模板

| 平台 | 文件 | 内部标题版本 | 标签版本 | 预定发布时间 | 24h播放 | 24h点赞 | 24h评论 | 7天结论 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| YouTube Shorts | `01-youtube-shorts-ai-script-prompt.mp4` | YT-A | 待填 | 待批准 | 待填 | 待填 | 待填 | 待填 | 仅人工回填 |
| 小红书 | `02-xiaohongshu-customer-reply-prompt.mp4` | XHS-A | 待填 | 待批准 | 待填 | 待填 | 待填 | 待填 | 仅人工回填 |
| B站 | `03-bilibili-quote-draft-prompt.mp4` | BILI-A | 待填 | 待批准 | 待填 | 待填 | 待填 | 待填 | 仅人工回填 |

## 下一步行动

1. 老板先审这 3 条无第三方水印样片的内容方向。
2. 若要进入真实发布候选，再按目标平台单独改标题、封面、标签和结尾文案。
3. 真实发布仍需老板明确批准，并由人工执行。
