# Qwen Image 3.0 集成配置

> 更新日期：2026-09-15  
> 模型：`qwen-image-3.0`  
> 地域：华北 2（北京）  
> 协议：DashScope 原生协议，默认同步调用

## 官方依据

- [阿里云百炼模型市场：Qwen-Image-3.0](https://bailian.console.aliyun.com/cn-beijing/model/market/detail/qwen-image-3.0?serviceSite=asia-pacific-china&ref=search_recommend)
- [千问图像生成模型 API 概览](https://help.aliyun.com/zh/model-studio/qwen-image-api)
- [千问图像生成与编辑 3.0 API 参考](https://help.aliyun.com/zh/model-studio/qwen-image-generation-and-editing-api-reference)

控制台模型页需要 JavaScript 和登录态，模型调用细节以上述同属阿里云的公开 API 参考为准。

## 已确认的模型约束

- 可用模型 ID：`qwen-image-3.0`、`qwen-image-3.0-pro`。
- `qwen-image-3.0` 兼顾生成质量与速度，本项目将其设为默认值。
- 同时支持文生图和 1-3 张参考图的图生图/编辑。
- 输出格式为 PNG，返回的临时 URL 有效期为 24 小时。本项目收到 URL 后立即下载到本地资产目录。
- 文生图输出像素面积范围为 512×512 至 2048×2048，宽高比为 1:8 至 8:1。
- 原生 DashScope 协议使用 `1280*720`，项目配置统一写 `1280x720`，Provider 在发送前转换。
- 提示词支持中英文，官方建议不超过 4500 Token。
- `seed` 范围为 0-2147483647。
- `prompt_extend_mode=agent` 仅用于文生图；加入参考图时应使用 `direct`。

## Endpoint 选择

官方建议华北 2（北京）使用业务空间专属域名：

```text
https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1
```

Workspace ID 可在百炼控制台的业务空间详情中查看。在未提供 Workspace ID 时，本项目使用仍受官方支持的公共地址：

```text
https://dashscope.aliyuncs.com/api/v1
```

同步接口（默认、官方推荐用于多数场景）：

```text
POST /services/aigc/multimodal-generation/generation
```

异步接口（适合批量任务）：

```text
POST /services/aigc/image-generation/generation
X-DashScope-Async: enable
GET /tasks/{task_id}
```

不要向同步 endpoint 添加异步请求头，也不要把异步 endpoint 用作同步调用。

## `.env` 配置

```dotenv
AI_VIDEO_DEFAULT_IMAGE_PROVIDER=dashscope

# 建议换成业务空间专属 URL；未配置 Workspace ID 时使用公共北京地址。
AI_VIDEO_DASHSCOPE_API_URL=https://dashscope.aliyuncs.com/api/v1
AI_VIDEO_DASHSCOPE_API_KEY=

AI_VIDEO_DASHSCOPE_IMAGE_MODEL=qwen-image-3.0
AI_VIDEO_DASHSCOPE_IMAGE_SIZE=1280x720

# 单张/少量生成默认同步。工作流批量稳定后才建议打开异步。
AI_VIDEO_DASHSCOPE_USE_ASYNC=false
AI_VIDEO_DASHSCOPE_PROMPT_EXTEND=true
AI_VIDEO_DASHSCOPE_PROMPT_EXTEND_MODE=direct
AI_VIDEO_DASHSCOPE_ENABLE_THINKING=true
AI_VIDEO_DASHSCOPE_WATERMARK=false
```

为了兼容现有本地配置，如果 `AI_VIDEO_DASHSCOPE_API_KEY` 为空，当前实现会回退读取 `AI_VIDEO_OPENAI_API_KEY`。新环境应使用专用的 `AI_VIDEO_DASHSCOPE_API_KEY`，不要混用变量名。

## 节点级可选配置

文生图节点可以覆盖全局默认值：

```json
{
  "provider": "dashscope",
  "image_model": "qwen-image-3.0",
  "size": "1280x720",
  "negative_prompt": "模糊，低清晰度，错误文字",
  "seed": 123456,
  "prompt_extend": true,
  "prompt_extend_mode": "direct",
  "enable_thinking": true,
  "watermark": false,
  "use_async": false,
  "generation_timeout": 600
}
```

## 已完成验证

- API Key 模型列表健康检查通过。
- 模型 ID `qwen-image-3.0` 存在，模型名区分大小写，不能写作 `Qwen-Image-3.0`。
- 原生同步接口真实生成 1280×720 PNG 成功。
- 生成结果已及时下载到 `data/assets/images/`，没有将 24 小时签名 URL 作为永久资产。
- Provider contract test 覆盖同步、异步、任务失败、URL/base64 响应和非法尺寸。

## 尚未完成

- 尚未配置业务空间专属域名；拿到 Workspace ID 后应替换公共 URL 并重新健康检查。
- 工作流多镜头真实批量生图仍受执行器 scene 数据传递进度影响。
- 图生图/编辑所需的 1-3 张输入图像 UI 尚未实现。
- API 成本预估、并发限制和批量调用确认仍需按主交付计划开发。
