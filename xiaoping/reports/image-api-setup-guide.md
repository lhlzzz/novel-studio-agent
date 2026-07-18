# 图像生成 API 配置指南

更新时间：2026-06-14

## 推荐方案：云雾 API (Yunwu)

云雾 API 是一个国内稳定的 AI API 中转站，支持：
- Google Gemini 图像生成
- OpenAI 图像生成
- 多种视频生成模型

### 注册步骤

1. **访问官网**：https://yunwu.ai
2. **注册账号**：点击右上角"注册"
3. **充值**：最低充值约 10 元人民币
4. **获取 API Key**：在"API Keys"页面创建

### 价格参考
- Gemini 图像生成：约 0.02-0.1 元/张
- 其他模型价格类似

## 备选方案：豆包 Seedream

字节跳动的图像生成服务，国内访问稳定。

### 注册步骤
1. **访问火山引擎**：https://www.volcengine.com
2. **开通豆包大模型**：在控制台开通
3. **获取 API Key**：在"API 密钥管理"页面创建

## 配置方法

### 方案1：云雾 API + Gemini

注册完成后，将 API Key 告诉我，我会帮你配置：

```yaml
image_generator:
  class_path: tools.ImageGeneratorNanobananaYunwuAPI
  init_args:
    api_key: YOUR_YUNWU_API_KEY
    model: gemini-2.5-flash-image-preview
    base_url: https://yunwu.ai
```

### 方案2：豆包 Seedream

```yaml
image_generator:
  class_path: tools.ImageGeneratorDoubaoSeedreamYunwuAPI
  init_args:
    api_key: YOUR_DOUBAO_API_KEY
    model: doubao-seedream-4-0-250828
```

## 下一步

1. 选择一个方案
2. 注册并获取 API Key
3. 将 API Key 告诉我
4. 我帮你配置并测试
