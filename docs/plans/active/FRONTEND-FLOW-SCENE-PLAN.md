# React Flow 与 Scene Prompt 产品化计划

> 状态：Active 子计划  
> 日期：2026-09-21
> 上级计划：[DELIVERY-PLAN.md](DELIVERY-PLAN.md)  
> 目标：把现有线性六节点画布升级为端口明确、可验证、可编辑、可导出的工作流与 Scene Prompt 系统。

## 0. 2026-09-21 实现检查点

| 工单 | 状态 | 当前证据 | 剩余工作 |
|---|---|---|---|
| FLOW-001 | 基础完成 | TS/Pydantic Node Manifest | 建立共享 JSON Schema/fixture 生成链 |
| FLOW-002 | 完成基础版 | StudioNode 多 Handle + 稳定 ID | 端口 hover/连接状态视觉 |
| FLOW-003 | 完成基础版 | 前后端 self/type/cardinality/cycle 校验 | create/update/start 强制调用与错误信封 |
| FLOW-004 | 完成基础版 | Toast、连接预览、高亮和 Chromium 主矩阵通过 | CI 归档 |
| FLOW-005 | 完成基础版 | EdgeInspector 已支持 label/mode/order/delete | reconnect 与执行语义验收 |
| FLOW-006 | 完成基础版 | WorkflowSpec 2.0 + v1 migration | DB/API/viewport roundtrip 验收 |
| FLOW-007 | 完成基础版 | onMoveEnd/saveViewport/自动布局存在 | CI roundtrip |
| FLOW-008 | 完成基础版 | begin/endBatchHistory 存在 | 多节点拖拽失败修复 |
| FLOW-009 | 完成基础版 | 多选/copy/paste/键盘操作存在 | 专项 E2E 深化 |
| FLOW-010 | 部分完成 | Chromium 连线/字段端口矩阵通过 | 全套 2 failed、1 skipped 待关闭 |
| SCENE-001 | 完成基础版 | TS/Pydantic ScenePromptBundle | 共用 fixture 与版本兼容测试 |
| SCENE-002 | 完成基础版 | Storyboard materializer | execution endpoint 主路径验收 |
| SCENE-003 | 部分 | CRUD/lock/merge API，内存 SceneService | SQLite migration/repository |
| SCENE-004 | 完成基础版 | `SceneEditor.tsx` 已挂载 | API 持久化与复杂批量编辑验收 |
| SCENE-005 | 完成基础版 | ExportDialog/ImportDialog + exporter | 下载响应与 roundtrip E2E |
| SCENE-006 | 后端完成 | Qwen JSONL exporter | Provider 参数完整性/前端预览 |
| SCENE-007 | 后端完成 | Wan3 JSONL exporter | firstFrame Asset ID 与 media 映射 |
| SCENE-008 | 完成基础版 | ExportDialog/ImportDialog 已存在 | 文件下载、错误和大文件体验 |
| SCENE-009 | 完成基础版 | secret/signed URL/path scanner | API 强制阻断策略 |
| SCENE-010 | 部分 | UI E2E 通过，JSON roundtrip 被 skip | 启动 backend 后取消 skip |

专项剩余重估：主要功能完成；2 人约 2-4 天关闭浏览器与联调门禁。

## 1. 当前实现评估

### 1.1 已实现

- React Flow 节点移动、缩放、平移、小地图和删除。
- 从左侧节点库拖入或点击添加节点。
- Node Manifest 和多命名 Handle 基础。
- sourceHandle/targetHandle 与 EdgeData 基础模型。
- 前后端图校验：类型、方向、cardinality、自环、重复边和环检测。
- WorkflowSpec 2.0 前端 migration 基础。
- Edge 创建、删除并随 WorkflowSpec 保存。
- 工作流 localStorage、SQLite、Undo/Redo、导入/导出。
- Storyboard 运行时输出 `Scene`，包含 scene_id、index、narration、image_prompt、video_prompt、duration 和 metadata。
- Scheduler 按 scene_id 为 map item 组装输入。
- Scene Prompt Bundle TS/Pydantic Schema、materializer、导出器、安全扫描和 API 基础。

### 1.2 关键缺口

#### React Flow 图契约

- Node Manifest 在前后端分别维护，尚无共享 JSON Schema/代码生成。
- 连接失败已有 Store/Toast 基础，但 `isValidConnection` 的前置拒绝未必进入 Store；仍缺端口高亮、inline 和可访问提示。
- EdgeData 已定义 mode/path/order/label，但没有 Edge 编辑器或执行语义完整验收。
- WorkflowSpec 2.0 migration 已有，viewport 实际保存和后端 roundtrip 待验收。
- Undo/Redo 记录 React Flow 临时变化，缺少语义事务。

#### Scene 与 Prompt

- Scene Bundle、导出器和 SceneEditor 已实现；API/SQLite roundtrip 仍需完整验收。
- Scene Draft 已有 migration/repository/API，需验证重启恢复和前端调用链。
- Qwen/Wan3 JSONL 后端导出器已存在，缺参数完整性验收和前端下载 UI。
- Scene lock/merge API 已有，缺真实执行主路径与用户交互验收。
- Schema 已提供 draft/execution/merged 来源字段，但产品 UI 尚未清晰展示“定义”和“运行结果”的区别。

## 2. 目标用户体验

### 2.1 连线

```text
拖动 source port
  → 只高亮类型/基数兼容的 target port
  → 放开后执行前端快速校验
  → 后端保存/运行前做权威校验
  → 不合法时保留画布并显示具体原因
```

节点可以拥有多个命名端口，例如：

```text
Storyboard
  input:  prompt:text
  output: scenes:list<scene>

ImageToVideo
  input:  image:image (required)
  input:  scene:scene (optional)
  input:  audio:audio (optional)
  output: video:video
```

### 2.2 Scene 编辑和导出

```text
执行 Storyboard 或导入 Scene Bundle
  → 打开 Scene Editor
  → 编辑 narration/image/video prompt 和时长
  → 锁定不希望重新生成的 scene
  → 校验 Provider 参数
  → 导出标准 Prompt Bundle / Markdown / JSONL
  → 重新送入下游图片和视频节点
```

## 3. 核心 Schema

### 3.1 Node Manifest

新增 `schemas/node-manifest.schema.json`：

```json
{
  "kind": "imageToVideo",
  "version": "1.0",
  "category": "video",
  "label": "图生视频",
  "ports": {
    "inputs": [
      {"id": "image", "type": "image", "required": true, "cardinality": "one"},
      {"id": "scene", "type": "scene", "required": false, "cardinality": "one"}
    ],
    "outputs": [
      {"id": "video", "type": "video", "cardinality": "one"}
    ]
  },
  "configSchema": {},
  "execution": {"mapOver": "image"}
}
```

端口类型首版：

```text
text, scene, image, video, audio, asset, any
list<T>
```

### 3.2 Edge Schema

```json
{
  "id": "edge-1",
  "source": "storyboard-1",
  "sourceHandle": "scenes",
  "target": "textToImage-1",
  "targetHandle": "scene",
  "type": "smoothstep",
  "data": {
    "mode": "map",
    "sourcePath": "$.scenes[*]",
    "targetPath": "$.scene",
    "itemKey": "scene_id",
    "order": 0,
    "label": "逐镜生成"
  }
}
```

`mode`：

- `direct`：一对一传递。
- `map`：数组逐项传递。
- `aggregate`：多项按 order/index 聚合。

首版不允许用户输入任意可执行表达式；JSONPath 只支持经过白名单校验的有限子集。

### 3.3 WorkflowSpec 2.0

```json
{
  "schemaVersion": "2.0",
  "manifestVersion": "1.0",
  "id": "...",
  "name": "...",
  "description": "...",
  "nodes": [],
  "edges": [],
  "viewport": {"x": 0, "y": 0, "zoom": 1},
  "metadata": {"tags": [], "createdBy": "user"}
}
```

必须提供 1.0 → 2.0 migration；旧 Edge 自动映射到默认 `in/out` Handle。

### 3.4 Scene Prompt Bundle

新增 `schemas/scene-prompt-bundle.schema.json`：

```json
{
  "schemaVersion": "1.0",
  "storyboardId": "storyboard-...",
  "workflowId": "workflow-...",
  "executionId": "exec-...",
  "title": "...",
  "globalStyle": "cinematic noir",
  "negativePrompt": "low quality, blurry",
  "scenes": [
    {
      "sceneId": "scene-001",
      "index": 0,
      "title": "雨夜出发",
      "narration": "...",
      "durationSeconds": 5,
      "locked": false,
      "image": {
        "prompt": "...",
        "negativePrompt": "...",
        "provider": "dashscope",
        "model": "qwen-image-3.0",
        "size": "1280x720",
        "seed": -1,
        "referenceAssetIds": []
      },
      "video": {
        "prompt": "...",
        "provider": "wan3",
        "model": "wan3.0-video",
        "resolution": "480P",
        "ratio": "adaptive",
        "duration": 5,
        "audio": true,
        "seed": -1,
        "firstFrameAssetId": null
      },
      "transition": {"type": "crossfade", "duration": 0.4},
      "metadata": {}
    }
  ]
}
```

Bundle 不包含 API Key、签名 URL 或本机绝对路径，只使用 Provider ID 和 Asset ID。

## 4. 导入导出类型

### 4.1 工作流定义导出

用途：分享和恢复画布，不包含运行时生成 scene。

- `workflow.json`：WorkflowSpec 2.0。
- `workflow-template.json`：清除 ID、执行状态和秘密引用。

### 4.2 Scene/Prompt 导出

来源必须明确：

- `draft`：手工编辑或导入的 Scene Bundle。
- `execution`：Storyboard 节点实际运行结果。
- `merged`：执行结果 + 用户覆盖/锁定值。

格式：

| 格式 | 用途 |
|---|---|
| `scene-prompt-bundle.json` | 标准、可重新导入 |
| `storyboard.md` | 人工审阅、脚本协作 |
| `scenes.csv` | 表格批量修改 |
| `qwen-image.jsonl` | 每行一个图片请求预览，不含 Key |
| `wan3-video.jsonl` | 每行一个视频请求预览，不提交任务 |
| `prompts.txt` | 纯 prompt 快速复制 |

Provider-specific 导出是“请求预览”，不是直接执行脚本。提交仍走受控 Provider。

### 4.3 API 规划

```text
GET  /api/executions/{id}/storyboard
POST /api/workflows/{id}/scene-drafts
GET  /api/workflows/{id}/scene-drafts/{draft_id}
PUT  /api/workflows/{id}/scene-drafts/{draft_id}
POST /api/workflows/{id}/scene-drafts/import
GET  /api/scene-bundles/{id}/export?format=json|markdown|csv|qwen_jsonl|wan3_jsonl|text
POST /api/scene-bundles/{id}/validate
```

下载响应携带 schema/version/content-disposition；大文件使用流式响应。

## 5. React Flow 详细工单

| ID | 优先级 | 工作量 | 任务 | 主要文件 | 验收 |
|---|---|---:|---|---|---|
| FLOW-001 | P0 | 2d | Node Manifest 与 Port TS/Pydantic Schema | `schemas/*`, `types.ts`, `domain/*` | 前后端共用 fixtures |
| FLOW-002 | P0 | 1.5d | 多 Handle 节点渲染，稳定 port ID/label/type | `StudioNode.tsx` | Edge 保存 handle ID |
| FLOW-003 | P0 | 2d | 连接校验器：方向、类型、基数、自环、重复边 | `graphValidation.ts`, backend validator | 错误码/文案一致 |
| FLOW-004 | P0 | 1d | 连接交互：兼容端口高亮、失败提示、连线预览 | `Canvas.tsx`, CSS | 键鼠均可完成 |
| FLOW-005 | P1 | 1.5d | Edge label、mode、order、选择/删除/重连 | `FlowEdge.tsx`, store | reconnect 保留数据 |
| FLOW-006 | P0 | 1.5d | WorkflowSpec 2.0 与 1.0 migration | schemas、models、migration | 旧工作流无损打开 |
| FLOW-007 | P1 | 1d | viewport 持久化、fit/center/auto-layout | `CanvasToolbar.tsx` | 刷新恢复视角 |
| FLOW-008 | P1 | 1.5d | 语义 Undo/Redo：拖动、连线、配置各一步 | `workflowStore.ts` | 连续拖动不刷爆历史 |
| FLOW-009 | P1 | 1d | 复制/粘贴、多选、键盘连线可访问性 | Canvas/store | ID 重写且边正确 |
| FLOW-010 | P0 | 2d | 图校验测试与 Playwright 连线 E2E | unit/e2e | 关键矩阵全覆盖 |

## 6. Scene Prompt 详细工单

| ID | 优先级 | 工作量 | 任务 | 主要文件 | 验收 |
|---|---|---:|---|---|---|
| SCENE-001 | P0 | 1.5d | Scene Prompt Bundle JSON Schema + TS/Pydantic | `schemas/*`, contracts | roundtrip fixture |
| SCENE-002 | P0 | 2d | Storyboard materializer：execution result → bundle | service/repository | scene_id/order 稳定 |
| SCENE-003 | P1 | 2d | Scene draft/override/lock 持久化 | migration/repository/API | 重启后恢复 |
| SCENE-004 | P1 | 3d | Scene Editor：列表/卡片、批量编辑、校验 | `SceneEditor/*` | 1-20 scenes 可编辑 |
| SCENE-005 | P0 | 1.5d | JSON/Markdown/CSV/Text 导入导出 | export service/API | roundtrip + UTF-8 |
| SCENE-006 | P1 | 1.5d | Qwen Image JSONL 请求预览 | exporter | 每 scene 一行，无 Key |
| SCENE-007 | P1 | 1.5d | Wan3 JSONL 请求预览 | exporter | first frame 用 Asset ID |
| SCENE-008 | P1 | 1d | 导出 UI：来源、格式、下载和错误 | toolbar/dialog | 文件名/版本正确 |
| SCENE-009 | P0 | 1d | 安全：秘密/签名 URL/绝对路径扫描 | validators/tests | 敏感字段拒绝导出 |
| SCENE-010 | P0 | 2d | Scene import/export API + 浏览器 E2E | api/e2e | 导入编辑再导出等价 |

## 7. 实施顺序

```text
FLOW-001/SCENE-001（契约冻结）
  → FLOW-002/003/006（端口和图版本）
  → SCENE-002/003（materialize 与持久化）
  → FLOW-004/005/007/008（画布体验）
  → SCENE-004/005/008（编辑和标准导出）
  → SCENE-006/007/009（Provider 预览与安全）
  → FLOW-010/SCENE-010（端到端门禁）
```

依赖原则：先冻结 Schema，再并行开发 UI/API；不允许先在前端发明字段再让后端追赶。

## 8. Sprint 建议

### Sprint F1：端口图契约（2 周）

范围：FLOW-001 至 006、FLOW-010 基础测试。

出口：多端口可连线、非法连接有原因、WorkflowSpec 2.0 可保存，旧图可迁移。

### Sprint F2：Scene Bundle 与编辑（2 周）

范围：SCENE-001 至 005、SCENE-009。

出口：执行结果可生成 Bundle，用户可编辑/锁定，JSON/Markdown/CSV/Text 可导入导出。

### Sprint F3：Provider Prompt 与画布打磨（1-2 周）

范围：FLOW-007 至 009、SCENE-006 至 010。

出口：Qwen/Wan3 JSONL 预览、视图恢复、语义历史和完整浏览器 E2E。

团队估算：2 人并行约 4-6 周；单人约 7-10 周。该估算应在 FLOW-001/SCENE-001 评审后重新基线。

## 9. 验收场景

1. Storyboard 的 `scenes` 只能连接到接收 scene/list<scene> 的端口。
2. 同一 cardinality=one 输入不能连接两条边。
3. 自环、重复边和成环操作立即拒绝并展示原因。
4. 保存/刷新后 sourceHandle、targetHandle、edge mode 和 viewport 不丢失。
5. v1 工作流自动迁移并保持执行结果一致。
6. 3 scene 执行结果导出 Bundle 后顺序和 scene_id 不变。
7. 编辑第 2 个 image prompt、锁定后再次生成不会覆盖。
8. JSON 导出再导入结构等价。
9. Qwen/Wan3 JSONL 不包含 Key、签名 URL 或绝对路径。
10. 中文 prompt 在 JSON/CSV/Markdown 中无乱码。

## 10. 明确不做

- 任意 JavaScript/Python 表达式边映射。
- 通用条件分支和嵌套循环。
- 在浏览器直接携带 Key 调用 Provider。
- 将 Provider-specific payload 作为唯一 Scene 存储格式。
- v1.0 中实现专业时间线和音频轨道编辑。
