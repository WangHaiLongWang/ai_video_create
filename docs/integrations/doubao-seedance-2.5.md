# Doubao Seedream / Seedance 2.5 集成

## 能力边界

项目中的 Provider 名称为 `doubao`，通过火山方舟 Ark API 提供两类能力：

- 文字生成图片：Seedream 图像模型；
- 文字生成视频、图片生成视频：Seedance 视频模型。

`Doubao-Seedance-2.5` 只配置在视频模型槽中。图片生成必须配置 Seedream 或方舟中等价的图像 Endpoint，不能把 Seedance 当作图片模型调用。

火山方舟控制台可能向用户提供 Endpoint ID，而不是直接接受公开模型名称。`DOUBAO_IMAGE_MODEL` 和 `DOUBAO_VIDEO_MODEL` 都按不透明字符串传递，可填写模型名或已开通的 Endpoint ID。

## 环境变量

```dotenv
AI_VIDEO_DEFAULT_IMAGE_PROVIDER=doubao
AI_VIDEO_DEFAULT_VIDEO_PROVIDER=doubao

AI_VIDEO_DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3
AI_VIDEO_DOUBAO_API_KEY=
AI_VIDEO_DOUBAO_IMAGE_MODEL=doubao-seedream-5-0-pro-260628
AI_VIDEO_DOUBAO_VIDEO_MODEL=doubao-seedance-2-5-260628
AI_VIDEO_DOUBAO_IMAGE_SIZE=1280x720
AI_VIDEO_DOUBAO_VIDEO_RESOLUTION=720p
AI_VIDEO_DOUBAO_VIDEO_RATIO=adaptive
AI_VIDEO_DOUBAO_VIDEO_DURATION=5
AI_VIDEO_DOUBAO_SEED=-1
AI_VIDEO_DOUBAO_WATERMARK=false
AI_VIDEO_DOUBAO_CAMERA_FIXED=false
AI_VIDEO_DOUBAO_POLL_INTERVAL=5
AI_VIDEO_DOUBAO_TIMEOUT=1800
```

API Key 不会由配置读取接口返回。设置页保存只修改当前进程内存；需要重启后保留时，应写入本地 `.env`，不要提交真实 Key。

## API 映射

| 能力 | Ark 路径 | 执行方式 |
|---|---|---|
| 文生图 | `POST /images/generations` | 同步返回 URL 或 base64 |
| 文生视频 | `POST /contents/generations/tasks` | 异步任务轮询 |
| 图生视频 | `POST /contents/generations/tasks` | content 加入 base64 首帧，异步轮询 |
| 任务查询 | `GET /contents/generations/tasks/{id}` | 直到 succeeded/failed |

生成结果 URL 可能短期有效，Provider 会立即下载并交给 AssetManager 持久化。视频外部任务 ID 会通过现有 Handler/Worker 链路进入任务记录。

## 可配置项

- 图像：模型/Endpoint、尺寸、seed、negative prompt、水印；
- 视频：模型/Endpoint、分辨率、比例、5/10 秒、seed、固定相机、水印；
- 运行：轮询间隔、任务超时；
- 输入：无图片时文生视频，有图片路径时图生视频。

具体支持的尺寸、分辨率、时长和模型名称以当前方舟控制台中已开通 Endpoint 为准。若供应商更新协议，只需调整 Provider adapter，不应把供应商 payload 泄漏到 WorkflowSpec。

2026-09-21 当前账号目录中已确认正式 ID：

```text
doubao-seedream-5-0-pro-260628
doubao-seedance-2-5-260628
```

目录可见不代表账号已经激活。真实请求若返回 `has not activated the model`，需要先在方舟控制台开通模型服务或创建 Endpoint。

## 验证

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\providers\test_doubao_provider.py -q
```

离线测试使用 `httpx.MockTransport`，不会产生真实计费调用。配置真实 Key 后，可在前端设置页选择 `doubao` 并使用“测试 Key 与端点”；健康检查只读取模型端点，不创建生成任务。
