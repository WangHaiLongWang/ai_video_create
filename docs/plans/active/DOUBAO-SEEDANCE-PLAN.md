# Doubao Seedream / Seedance 2.5 接入与验收计划

> 状态：Active，等待火山方舟模型服务激活
> 日期：2026-09-21
> Provider：`doubao`
> 关联文档：[Doubao 集成说明](../../integrations/doubao-seedance-2.5.md)

## 1. 交付目标

将火山方舟作为可插拔媒体 Provider 接入现有工作流：

```text
Scene image_prompt
  → textToImage / Doubao Seedream
  → Asset(image, scene_id, variant_id)
  → imageToVideo / Doubao Seedance 2.5
  → Asset(video, scene_id, variant_id, external_job_id)
  → videoConcat
```

支持文字生成图片、文字生成视频和图片生成视频。

## 2. 2026-09-21 验证结果

| 检查项 | 结果 | 证据/说明 |
|---|---|---|
| API Key 加载 | 通过 | Key 存在，日志未输出明文 |
| Ark `/models` 访问 | 通过 | 认证和网络正常 |
| Seedream 正式 ID | 已确认 | `doubao-seedream-5-0-pro-260628` |
| Seedance 2.5 正式 ID | 已确认 | `doubao-seedance-2-5-260628` |
| Seedream 真实生图 | Blocked | 账号尚未激活该模型服务，HTTP 404 |
| Seedance 2.5 文生视频 | Blocked | 账号尚未激活该模型服务，HTTP 404 |
| Seedance 2.5 图生视频 | 未执行 | 生图未成功，且视频模型权限已确认阻断 |
| 离线 Provider Contract | 通过 | Doubao + Config API 16 passed；全部 providers 43 passed |
| 前端 typecheck/build | 通过 | 设置页可选 `doubao`，生产构建成功 |

本次请求未创建成功的图片/视频任务，没有可交付媒体文件。

## 3. 外部前置条件

在火山方舟控制台完成以下任一方式：

- 激活 `doubao-seedream-5-0-pro-260628` 和 `doubao-seedance-2-5-260628` 模型服务；或
- 为两个模型分别创建在线推理 Endpoint，并将 Endpoint ID 写入 `.env`。

同时确认 API Key 所属项目一致、账户余额和地域正确、Endpoint 正在运行，视频配额允许至少一个 5 秒 720p 任务。

## 4. 复测步骤

### DOU-UAT-001：认证与目录

```powershell
backend\.venv\Scripts\python.exe scripts\smoke_doubao.py health
backend\.venv\Scripts\python.exe scripts\smoke_doubao.py models
```

### DOU-UAT-002：文字生成图片

```powershell
backend\.venv\Scripts\python.exe scripts\smoke_doubao.py image
```

通过标准：保存 `data/assets/doubao-uat/seedream-ski.png`；文件大于 10 KB且可解码；报告不记录 Key 或签名 URL；画面满足“两个人、冬季滑雪教学、背景无其他人”。

### DOU-UAT-003：图片生成视频

```powershell
backend\.venv\Scripts\python.exe scripts\smoke_doubao.py video
```

通过标准：保存 `data/assets/doubao-uat/seedance-ski.mp4`；记录外部任务 ID；ffprobe 可读且约 5 秒；首帧主体一致；临时 URL 不进入日志和 WorkflowSpec。

### DOU-UAT-004：Workflow 纵向验收

```text
textInput → storyboard(1 scene)
→ textToImage(1 variant)
→ imageToVideo(5s)
→ videoConcat → output
```

通过标准：节点状态、scene_id/variant_id、资产血缘、外部任务 ID、失败重试和最终下载全部正确。

## 5. 后续研发工单

| ID | 优先级 | 工作量 | 内容 | 验收 |
|---|---:|---:|---|---|
| DOU-001 | P0 | 外部 | 激活两个模型或创建 Endpoint | 真实请求不再返回未激活 |
| DOU-002 | P0 | 0.5d | 完成 image/video smoke 并记录报告 | UAT-002/003 通过 |
| DOU-003 | P0 | 1d | 工作流纵向 UAT | UAT-004 通过 |
| DOU-004 | P1 | 0.5d | 区分“认证正常/模型未激活” | 设置页显示可行动错误 |
| DOU-005 | P1 | 1d | Ark 错误码映射与 retryable 分类 | 401/403/404/429/5xx 覆盖 |
| DOU-006 | P1 | 1d | 视频任务重启恢复和取消 | 重启续轮询，取消拒绝迟到结果 |
| DOU-007 | P1 | 0.5d | 成本预估和并发限制 | 运行前显示调用数 |
| DOU-008 | P1 | 1d | Settings/API/E2E | 选择、保存、恢复、测试连接通过 |

## 6. 发布门禁

在以下条件满足前，Doubao 只能标记为 `Contract Ready / External Blocked`：

- DOU-UAT-002、003、004 全部通过；
- 真实结果经过人工内容验收；
- 429、超时、失败、取消和下载失败有明确错误；
- Key 不出现在响应、日志、导出文件和 Git；
- 同一 commit 至少一次完整工作流可重复成功。

## 7. 回滚

```dotenv
AI_VIDEO_DEFAULT_IMAGE_PROVIDER=dashscope
AI_VIDEO_DEFAULT_VIDEO_PROVIDER=wan3
```

切换 Provider 不改变 WorkflowSpec，历史资产保持可读，不自动删除失败任务或生成文件。
