# ViMax 集成状态

更新时间：2026-06-14

## 已完成

- ✅ ViMax 仓库已克隆到 `tools/external/repos/ViMax`
- ✅ 依赖已安装（`uv sync`）
- ✅ 配置文件已创建（`configs/idea2video_openrouter.yaml`）
- ✅ 包装器脚本已创建（`xiaoping_wrapper.py`）
- ✅ TOOLING.md 已更新

## 待解决

### 图像生成 API
ViMax 需要图像生成 API，当前有以下选项：

| 选项 | 需要 | 状态 |
|------|------|------|
| Google API | Google API Key | ❌ 未配置 |
| 云雾 API (Yunwu) | 云雾 API Key | ❌ 未配置 |
| 豆包 Seedream | 豆包 API Key | ❌ 未配置 |

### 推荐方案
1. **申请云雾 API**：支持 Gemini 图像生成，价格较低
2. **申请豆包 API**：支持 Seedream 图像生成，国内服务
3. **使用 Google API**：需要科学上网

## ViMax 功能

| 功能 | 说明 | 状态 |
|------|------|------|
| Idea2Video | 想法→视频 | ⚠️ 需要图像API |
| Script2Video | 剧本→视频 | ⚠️ 需要图像API |
| Novel2Video | 小说→视频 | ⚠️ 需要图像API |
| AutoCameo | 照片→视频 | ⚠️ 需要图像API |

## 下一步

1. 选择并配置图像生成 API
2. 测试 ViMax 视频生成
3. 集成到 xiaoping 视频生产流程

## 替代方案

如果暂时无法配置 ViMax 图像 API，可以继续使用：
- **MoneyPrinterTurbo**：已验证可用，生成字幕+素材拼接视频
- **Remotion**：程序化视频生成
- **Pixelle-Video**：静态模板+TTS
