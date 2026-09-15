# 万相 3.0 视频生成配置

> 更新日期：2026-09-15  
> 默认模型：`wan3.0-video`  
> 默认清晰度：`480P`  
> 地域：华北 2（北京）  
> Provider 名称：`wan3`

## 官方依据

- [阿里云百炼模型市场：万相 3.0 视频](https://bailian.console.aliyun.com/cn-beijing/model/market/detail/wan3.0-video)
- [万相 3.0 视频生成 API 参考](https://docs.bailian.console.aliyun.com/zh/model-studio/wan3-video-generation-api-reference)

## 架构边界

万相 3.0 是百炼云端视频生成服务，不是 ComfyUI 工作流。本项目保留两个独立 Provider：

- `comfyui`：连接本机或局域网 ComfyUI，执行用户安装的 workflow。
- `wan3`：连接阿里云百炼，提交 Wan3.0 异步视频任务。

二者都可以作为 `imageToVideo` 节点的 Provider，但 endpoint、认证、参数和任务状态互不混用。

## 官方参数

### 模型

- `wan3.0-video`：标准版，本项目默认值。
- `wan3.0-video-prime`：高速版，能力对齐标准版。

### 输入

- `prompt`：中文或英文，最多 20000 字符。
- `media`：可选素材数组。图生视频默认使用：

```json
{"type": "first_frame", "url": "data:image/png;base64,..."}
```

Wan3 还支持 `last_frame`、`reference_image`、`reference_video`、`reference_audio`、`file` 和 `link`。v1 工作流的图片转视频节点只开放 `first_frame`，其余类型留给后续参考生视频节点。

首帧图片支持 JPEG/JPG/PNG（不支持透明通道）/BMP/WEBP，单边 240-8000 像素，宽高比不超过 8:1，大小不超过 20MB。当前 Provider 会限制文件类型和大小；透明通道检查需在后续媒体校验任务补齐。

### 生成参数

| 参数 | 默认值 | 可选值/范围 | 说明 |
|---|---|---|---|
| `resolution` | `480P` | `480P`, `720P`, `1080P` | 官方默认是 1080P，本项目为降低开发期成本改为 480P |
| `ratio` | `adaptive` | `adaptive`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16` | 自适应会参考输入媒体比例 |
| `duration` | `5` | `-1` 或 2-30 秒整数 | `-1` 为智能时长；有参考视频时总时长不能超过 30 秒 |
| `audio` | `true` | boolean | 是否生成音轨；官方说明开关声音价格相同 |
| `seed` | `-1` | `-1` 或 0-2147483647 | 相同 seed 也不保证结果完全一致 |
| `prompt_extend` | `true` | boolean | 智能改写较短提示词，会增加耗时 |
| `watermark` | `false` | boolean | 是否增加模型水印 |

### 异步协议

创建任务：

```text
POST /services/aigc/video-generation/video-synthesis
X-DashScope-Async: enable
```

查询任务：

```text
GET /tasks/{task_id}
```

`task_id` 查询有效期为 24 小时。不要因为客户端等待而重复创建任务；应保存 task_id 并继续轮询。当前 Provider 在单次 Handler 中轮询，后续需要把 task_id 持久化到 node_run，才能完全满足进程重启恢复要求。

## `.env` 配置

```dotenv
AI_VIDEO_DEFAULT_VIDEO_PROVIDER=wan3

# 官方建议使用带 Workspace ID 的北京业务空间专属域名。
AI_VIDEO_WAN3_API_URL=https://dashscope.aliyuncs.com/api/v1
AI_VIDEO_WAN3_API_KEY=sk-your-key

AI_VIDEO_WAN3_MODEL=wan3.0-video
AI_VIDEO_WAN3_RESOLUTION=480P
AI_VIDEO_WAN3_RATIO=adaptive
AI_VIDEO_WAN3_DURATION=5
AI_VIDEO_WAN3_AUDIO=true
AI_VIDEO_WAN3_SEED=-1
AI_VIDEO_WAN3_PROMPT_EXTEND=true
AI_VIDEO_WAN3_WATERMARK=false
AI_VIDEO_WAN3_POLL_INTERVAL=5
AI_VIDEO_WAN3_TIMEOUT=1800
```

生产环境建议将 URL 换为：

```text
https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1
```

如果 `AI_VIDEO_WAN3_API_KEY` 为空，当前实现会依次回退到 `AI_VIDEO_DASHSCOPE_API_KEY`、`AI_VIDEO_OPENAI_API_KEY`。新环境应配置专用 `AI_VIDEO_WAN3_API_KEY`。

## ComfyUI 配置

如果需要本地视频生成，设置：

```dotenv
AI_VIDEO_DEFAULT_VIDEO_PROVIDER=comfyui
AI_VIDEO_COMFYUI_API_URL=http://localhost:8188
```

当前 ComfyUI `_build_img2vid_workflow()` 仍是占位 workflow，必须替换成实际安装节点导出的 API workflow JSON 后才能用于真实视频生成。Wan3 云端配置不会自动安装或配置 ComfyUI 节点。

## 当前验证状态

- 官方文档参数和 endpoint 已核对。
- Provider Contract Test 覆盖 480P 默认值、首帧 Base64、任务轮询、结果下载和非法参数。
- 已配置的百炼 Key 对公共 endpoint 鉴权健康检查通过。
- 模型列表 endpoint 未返回 `wan3.0-video`，该列表不能作为视频模型授权依据。
- **尚未创建真实 Wan3 视频任务**。视频调用耗时长且会计费，需由用户明确确认后执行最小 480P/2 秒测试。
- 运行时 task_id 尚未持久化，进程重启恢复列为主交付计划的 Provider JobHandle 工作。

