# ADR-0001：按能力拆分外部生成 Provider

> 状态：Accepted  
> 日期：2026-09-15  
> 决策人：项目维护者  
> 关联：Qwen Image 3.0、Wan3.0 Video、ComfyUI

## 背景

项目需要同时接入本地与云端的文本、图像和视频服务。早期设计以 `Mock/Real Handler` 全局开关和单个 ComfyUI 类承载图像/视频能力，容易产生以下问题：

- 默认 LLM 为 Mock 时，真实图像或视频 Provider 不会注册。
- 百炼 Wan3.0 被误认为 ComfyUI workflow 配置。
- 不同服务的认证、endpoint、同步/异步状态和参数混入 Handler。
- 用户无法组合使用 Mock LLM、Qwen Image 和 Wan3 Video。

## 决策

Provider 按能力独立注册和选择：

```text
text  → mock | ollama | openai | openai_compat（MiMo 预设）
image → mock | dashscope(qwen-image-3.0) | openai | comfyui
video → mock | wan3(wan3.0-video) | comfyui
```

默认开发组合：

```text
text=mock
image=dashscope/qwen-image-3.0/1280x720
video=wan3/wan3.0-video/480P
```

职责边界：

- Provider：适配认证、请求/响应、远程 task 和结果下载。
- Handler：实现 TextInput、Storyboard、TextToImage、ImageToVideo 等节点语义。
- Scheduler：组装上游 NodeResult、map/aggregate、重试、取消和恢复。
- Asset Service：持久化外部结果和血缘，不保留临时 URL 作为永久输出。

Wan3 与 ComfyUI 保持两个不同 Provider：

- `wan3` 使用百炼 `video-synthesis` 和 `/tasks/{task_id}`。
- `comfyui` 使用 `/prompt`、`/history/{prompt_id}` 和 `/view`。

## 后果

正面：

- 用户可以按节点能力自由组合不同后端。
- Provider 的 Contract Test 可以独立覆盖。
- Wan3 task_id 与 ComfyUI prompt_id 可以分别建模。
- 配置和 UI 不再隐式依赖默认 LLM。

成本：

- Provider Registry 需要 capability 查询和生命周期管理。
- Node Manifest 需要声明所需 capability。
- 长任务恢复需要统一 JobHandle，但仍保留 Provider-specific external_job_id。
- 设置页需要按 Provider 动态显示不同配置项。

## 被否决方案

### 将 Wan3 配进 ComfyUIProvider

否决。Wan3 是百炼云端服务，协议和 ComfyUI 不兼容。除非用户自己安装一个调用百炼的 ComfyUI 自定义节点并提供对应 workflow，否则不能称为 ComfyUI 原生 Wan3 配置。

### 继续使用全局 Mock/Real Handler 开关

否决。它无法支持 text=mock、image=dashscope、video=wan3 的组合，也是此前图像 Provider 未注册的根因。

### 所有服务统一命名为 OpenAI-compatible

否决。Qwen Image 3.0 虽支持特定 OpenAI Images 兼容模式，但生产专属域名、扩展参数和同步行为与通用 OpenAI API 不完全相同；Wan3 更是异步原生视频协议。

## 验证

- Qwen Image 3.0 真实 1280×720 PNG 生成通过。
- Wan3 Provider 鉴权、480P 参数、首帧 Base64、任务轮询和下载 Contract Test 通过。
- 运行时可以同时注册 `mock`、`dashscope` 和 `wan3`。
- 真实 Wan3 计费 UAT 和 ComfyUI 本机 workflow UAT 尚待执行。
