# Xiaomi MiMo v2.5 Pro LLM 配置

> 更新日期：2026-09-15  
> Provider：`openai_compat`  
> 默认预设：Xiaomi MiMo  
> 模型：`mimo-v2.5-pro`

## 官方依据

- [Xiaomi MiMo：首次 API 调用](https://mimo.mi.com/docs/zh-CN/quick-start/summary/first-api-call)

## 按量 API 配置

```text
Base URL  https://api.xiaomimimo.com/v1
Endpoint  POST /chat/completions
Header    api-key: sk-xxxxx
Model     mimo-v2.5-pro
```

官方示例使用：

```json
{
  "model": "mimo-v2.5-pro",
  "messages": [],
  "max_completion_tokens": 1024,
  "temperature": 1.0,
  "top_p": 0.95,
  "stream": false
}
```

项目默认将最大输出设为 4096，便于生成结构化分镜；节点配置仍可覆盖。若需要严格采用官方快速开始的最小值，可将 `AI_VIDEO_OPENAI_COMPAT_MAX_TOKENS` 改为 1024。

## Token Plan 配置

订阅 Token Plan 时使用专属配置：

```text
Base URL  https://token-plan-cn.xiaomimimo.com/v1
API Key   tp-xxxxx
```

模型和其余请求字段保持一致。不要把按量 `sk-` Key 与 Token Plan `tp-` Key/Base URL 混用。

## `.env` 配置

仓库示例文件中的 Key 保持为空：

```dotenv
AI_VIDEO_DEFAULT_LLM_PROVIDER=openai_compat

AI_VIDEO_OPENAI_COMPAT_NAME=Xiaomi MiMo
AI_VIDEO_OPENAI_COMPAT_API_URL=https://api.xiaomimimo.com/v1
AI_VIDEO_OPENAI_COMPAT_API_KEY=
AI_VIDEO_OPENAI_COMPAT_MODEL=mimo-v2.5-pro

AI_VIDEO_OPENAI_COMPAT_AUTH_HEADER=api-key
AI_VIDEO_OPENAI_COMPAT_AUTH_SCHEME=
AI_VIDEO_OPENAI_COMPAT_MAX_TOKENS_PARAM=max_completion_tokens

AI_VIDEO_OPENAI_COMPAT_MAX_TOKENS=4096
AI_VIDEO_OPENAI_COMPAT_TEMPERATURE=1.0
AI_VIDEO_OPENAI_COMPAT_TOP_P=0.95
AI_VIDEO_OPENAI_COMPAT_TIMEOUT=120
```

填写 Key 后重启服务，或在设置面板中保存并测试连接。设置 API 当前只更新内存，持久配置仍以 `.env` 为准。本机 `.env` 当前使用 Token Plan Base URL；该文件已被 gitignore，不纳入仓库文档示例。

## 自定义 OpenAI-compatible Provider

同一配置槽可替换为其他兼容 Chat Completions 的服务：

- `OPENAI_COMPAT_NAME`：界面显示名称。
- `OPENAI_COMPAT_API_URL`：包含版本路径的 Base URL。
- `OPENAI_COMPAT_MODEL`：模型 ID。
- `OPENAI_COMPAT_AUTH_HEADER`：例如 `api-key` 或 `Authorization`。
- `OPENAI_COMPAT_AUTH_SCHEME`：MiMo 留空；标准 Bearer 服务填 `Bearer`。
- `OPENAI_COMPAT_MAX_TOKENS_PARAM`：`max_tokens` 或 `max_completion_tokens`。
- temperature、top_p、最大输出和 timeout。

该 Provider 只声明 text capability，不会错误地出现在图像或视频 Provider 列表。

## 安全边界

- `.env` 已被 gitignore；`.env.example` 不包含 Key。
- Settings GET 不返回 API Key。
- Provider 日志不打印认证头和 Key。
- 自定义 Header 禁止 CR/LF，防止 Header 注入。
- Base URL 必须使用 HTTP/HTTPS；生产配置建议只使用可信 HTTPS endpoint。

## 验证状态

- MiMo 请求 Contract Test 已覆盖：`api-key`、`mimo-v2.5-pro`、`max_completion_tokens`、temperature 和 top_p。
- 通用 Bearer 模式构造测试已覆盖。
- 本机 API Key 已由用户配置，运行时 Provider 注册成功，Settings GET 不暴露 Key。
- MiMo `/models` 网络健康检查通过。
- `mimo-v2.5-pro` Chat Completions 真实调用通过：HTTP 200、`finish_reason=stop`，同时返回 `reasoning_content` 和最终 `content`。
- 最小 32 completion tokens 请求只产生推理、最终 `content` 为空；256 tokens 请求成功产生最终回答。项目默认 4096，适合结构化分镜任务。
