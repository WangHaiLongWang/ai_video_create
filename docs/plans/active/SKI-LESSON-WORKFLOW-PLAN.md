# 写实冬季滑雪教学工作流开发计划

> 状态：Active 验收工作流  
> 日期：2026-09-17  
> 上级计划：[DELIVERY-PLAN.md](DELIVERY-PLAN.md)  
> 相关专项：[FRONTEND-FLOW-SCENE-PLAN.md](FRONTEND-FLOW-SCENE-PLAN.md)  
> 目标：用一个可插拔模板跑通 MiMo → Qwen Image ×2 → Wan3 3 秒 ×2 → FFmpeg 合成。

## 1. 业务目标

输入一段中文滑雪教学描述，生成：

1. 一个结构化教学 Scene；
2. 两张保持人物数量、动作和场景约束的写实电影感照片；
3. 每张照片分别生成 3 秒首帧视频；
4. 默认按变体顺序拼接为约 6 秒 MP4；
5. 每个文本、图片、视频片段和最终视频具有可追踪血缘；
6. 整个流程可以保存为模板、更换 Provider、调整变体数量或切换输出策略。

### 输出策略

首版默认：

```text
two_variants_to_video
2 images → 2 × 3s clips → concat ≈ 6s final video
```

预留策略：

```text
best_of_two
2 images → user/quality selector chooses 1 → 1 × 3s video
```

`best_of_two` 需要 ImageSelector 节点，不作为首个跑通门禁。

## 2. 内容规格

### 2.1 原始创作要求

```text
写实电影感冬季滑雪教学场景，晴朗白天，初级雪道平缓雪地。
画面中只有两个人：一位单板滑雪教练和一位初学者学员。
教练在左侧，单板，双脚固定，半蹲，一手前伸指向学员前脚固定器，正在耐心讲解；
学员在右侧，单板，仅前脚固定在固定器中，后脚自由，踩在雪地上准备蹬行，膝盖微屈，身体侧向，视线看向前方，板头指向滑行方向。
雪面有滑痕和飞溅雪粒，远处雪山和缆车虚化。
中景，低机位，35mm 镜头，浅景深，自然光，4K，超写实，高细节，冬季运动摄影。
背景无其他人。
```

### 2.2 正向图像 Prompt

```text
写实电影感冬季单板滑雪教学照片，晴朗白天，平缓的初级雪道。画面严格只有两个人，背景没有任何其他人物。

左侧是一位单板滑雪教练，双脚都固定在同一块单板滑雪板的固定器中，保持稳定半蹲姿势，一只手向前伸出，手指明确指向右侧学员的前脚固定器，神态专注耐心，正在讲解如何单脚蹬行。

右侧是一位初学者学员，站在自己的单板滑雪板上，仅前脚固定在前脚固定器内，后脚完全未固定并踩在雪地上准备蹬行；膝盖微屈，身体侧向，视线看向前方，板头清晰指向预定滑行方向。两人的滑雪板彼此独立，装备结构合理，肢体与固定器关系清晰准确。

雪面有真实滑痕和轻微飞溅雪粒，远处雪山与缆车自然虚化。中景，低机位，35mm 镜头，浅景深，自然阳光，真实雪地反射，电影级色彩，4K，超写实，高细节，专业冬季运动摄影，清晰准确的人体比例、手脚和单板固定器。
```

### 2.3 负向图像 Prompt

```text
第三个人，背景人物，人群，其他滑雪者，多余人物，双板滑雪，滑雪杖，两人共用一块单板，学员双脚都固定，学员后脚固定在板上，教练脚未固定，错误固定器，额外的腿，额外的手，多余手指，肢体融合，手指方向错误，板头方向错误，单板断裂，装备漂浮，错误透视，卡通，插画，CG 感，低清晰度，模糊，过曝，文字，标志，水印
```

### 2.4 图片变体

两个变体共享上述人物、动作、装备与环境约束，只允许轻微摄影变化：

| 变体 | 追加 Prompt | 不允许变化 |
|---|---|---|
| `variant-01` | 略偏教练方向的低机位三分之四侧视角，突出教练指向固定器的手势 | 人数、左右位置、脚的固定状态、板头方向 |
| `variant-02` | 低机位略宽中景，学员单脚蹬行准备姿态更清晰，雪粒略有动态 | 人数、动作语义、装备关系、背景无人 |

### 2.5 视频 Prompt

```text
保持首帧中的两个人、左右位置、服装、单板和固定器结构完全一致。镜头进行非常轻微、平稳的低机位前推。左侧教练保持半蹲，一只手继续指向学员前脚固定器并做小幅自然讲解手势；右侧学员前脚保持固定、后脚保持自由并在雪地上轻轻蹬行一次，膝盖微屈，板头持续朝向滑行方向。雪面产生少量真实雪粒，远处雪山与缆车保持虚化。不要新增人物，不要切镜，不要改变装备，不要让后脚自动固定，不要改变为双板滑雪。写实电影感，自然日光，运动摄影，时长 3 秒。
```

## 3. 工作流设计

### 3.1 目标图

```text
[TextInput: skiing_brief]
      text
        ↓
[Storyboard: scene_count=1]
      scenes
        ↓ map(scene_id)
[TextToImage: variants=2]
      images (scene_id + variant_id)
        ↓ map(asset_id)
[ImageToVideo: duration=3s, resolution=480P]
      videos (scene_id + variant_id)
        ↓ aggregate(order=variant_index)
[VideoConcat]
      video
        ↓
[Output]
```

### 3.2 稳定端口

| 节点 | 输入端口 | 输出端口 |
|---|---|---|
| TextInput | 无 | `text:text` |
| Storyboard | `prompt:text` | `scenes:scene[many]` |
| TextToImage | `scene:scene` | `images:image[many]` |
| ImageToVideo | `image:image`, `scene:scene?` | `video:video` |
| VideoConcat | `videos:video[many]` | `video:video` |
| Output | `video:video` | 无 |

### 3.3 Edge 语义

| 连线 | mode | item key | 顺序 |
|---|---|---|---|
| TextInput → Storyboard | direct | 无 | 0 |
| Storyboard → TextToImage | map | `scene_id` | scene.index |
| TextToImage → ImageToVideo | map | `scene_id + variant_id` | variant.index |
| Storyboard → ImageToVideo.scene | direct-by-key | `scene_id` | 0 |
| ImageToVideo → VideoConcat | aggregate | `scene_id + variant_id` | variant.index |
| VideoConcat → Output | direct | 无 | 0 |

当前 Edge mode 尚未完全进入执行器主路径，本工作流是 FLOW/SCENE 专项的第一条真实验收用例。

## 4. Scene Bundle 实例

```json
{
  "schemaVersion": "1.0",
  "storyboardId": "ski-lesson-storyboard",
  "workflowId": "template-ski-lesson",
  "executionId": "",
  "title": "冬季单板滑雪单脚蹬行教学",
  "globalStyle": "写实电影感，晴朗冬季白天，低机位35mm，自然光，浅景深，4K冬季运动摄影",
  "negativePrompt": "第三个人，背景人物，人群，双板滑雪，错误固定器，肢体畸形，文字，水印",
  "source": "draft",
  "scenes": [
    {
      "sceneId": "scene-001",
      "index": 0,
      "title": "单脚蹬行姿势讲解",
      "narration": "教练讲解前脚固定、后脚自由的单脚蹬行准备姿势。",
      "durationSeconds": 3,
      "locked": true,
      "image": {
        "prompt": "<使用 2.2 正向图像 Prompt>",
        "negativePrompt": "<使用 2.3 负向图像 Prompt>",
        "provider": "dashscope",
        "model": "qwen-image-3.0",
        "size": "1280x720",
        "seed": -1,
        "referenceAssetIds": []
      },
      "video": {
        "prompt": "<使用 2.5 视频 Prompt>",
        "provider": "wan3",
        "model": "wan3.0-video",
        "resolution": "480P",
        "ratio": "16:9",
        "duration": 3,
        "audio": false,
        "seed": -1,
        "firstFrameAssetId": null
      },
      "transition": {"type": "crossfade", "duration": 0.3},
      "metadata": {
        "variantCount": 2,
        "outputStrategy": "two_variants_to_video",
        "peopleCount": 2,
        "backgroundPeopleAllowed": false
      }
    }
  ]
}
```

## 5. 可插拔能力设计

### 5.1 Template 插件

新增内置模板 ID：`realistic-ski-lesson`。

模板参数：

```json
{
  "imageProvider": "dashscope",
  "imageModel": "qwen-image-3.0",
  "imageSize": "1280x720",
  "variantCount": 2,
  "videoProvider": "wan3",
  "videoModel": "wan3.0-video",
  "videoResolution": "480P",
  "videoDuration": 3,
  "videoAudio": false,
  "outputStrategy": "two_variants_to_video"
}
```

模板本身不写 Key，不写签名 URL，不写本机路径。

### 5.2 图像变体插件

通用字段：

```json
{
  "variantCount": 2,
  "variantMode": "prompt_suffix",
  "variants": [
    {"id": "variant-01", "promptSuffix": "..."},
    {"id": "variant-02", "promptSuffix": "..."}
  ]
}
```

Task item key：`scene-001::variant-01`。Asset 同时记录 scene_id 与 variant_id。

该能力必须适用于任何 T2I Provider，不在 Qwen Handler 中硬编码。

### 5.3 输出策略插件

- `all`：所有图片都进入视频生成。
- `manual_select`：暂停执行，等待用户选择。
- `quality_select`：调用评分器自动选优，v1.1 再做。

首版实现 `all`，接口保留策略字段。

## 6. 缺口与开发工单

| ID | 优先级 | 工作量 | 任务 | 主要文件 | 验收 |
|---|---|---:|---|---|---|
| SKI-001 | P0 | 0.5d | 固化 Prompt/Scene Bundle fixture | `templates/`, `tests/fixtures/` | Schema 校验通过 |
| SKI-002 | P0 | 1d | 新增 `realistic-ski-lesson` 模板和参数注入 | `services/templates.py`, API | 加载后图与配置正确 |
| SKI-003 | P0 | 2d | T2I `variantCount/variants` 通用 fan-out | compiler/scheduler/handlers | 1 scene → 2 image tasks |
| SKI-004 | P0 | 1.5d | `variant_id` 进入 NodeResult/Asset/Task 血缘 | contracts/migration/repository | 查询链完整 |
| SKI-005 | P0 | 1.5d | I2V 按 scene+variant 取图片和视频 prompt | scheduler/handler | 2 image → 2 video tasks |
| SKI-006 | P0 | 1d | Wan3 节点级 3 秒/480P/16:9/无音轨参数 | manifest/form/provider | payload 与配置一致 |
| SKI-007 | P0 | 1.5d | aggregate 按 variant.index 拼接 | compiler/scheduler/concat | 最终时长约 6 秒 |
| SKI-008 | P1 | 1d | 模板参数 UI 与调用量/成本确认 | TemplateSelector/dialog | 显示 2 图 + 2 视频调用 |
| SKI-009 | P1 | 1d | Scene/Variant 预览与单项重试 | SceneEditor/AssetPanel | 可重试任一变体 |
| SKI-010 | P0 | 2d | Mock 全链验收 | acceptance/E2E | 1→2→2→1 任务链 |
| SKI-011 | P0 | 1.5d | Qwen 真实两图 UAT | integration/report | 两张 PNG，均仅两人 |
| SKI-012 | P0 | 2d | Wan3 两段 3 秒 + FFmpeg UAT | integration/report | 两段可播放，最终约 6 秒 |
| SKI-013 | P1 | 1d | 内容约束人工验收表 | `docs/reports/` | 每张图片逐项签字 |
| SKI-014 | P0 | 1d | Bundle/Qwen/Wan3 JSONL 导出验收 | scenes API/E2E | 无秘密，可重导入 |

总估算：17.5 人日，不含外部 API 排队和人工返工。2 人约 2 周，单人约 3-4 周。

## 7. 开发顺序

```text
SKI-001/002（模板与 fixture）
  → SKI-003/004（图片变体 fan-out 与血缘）
  → SKI-005/006（视频输入和参数）
  → SKI-007（聚合合成）
  → SKI-008/009（产品 UI）
  → SKI-010/014（Mock 与导出门禁）
  → 用户确认成本
  → SKI-011/012/013（真实 UAT）
```

真实 UAT 之前必须先用 Mock 验证任务数、输入内容、参数和资产血缘，防止错误批量计费。

## 8. 验收标准

### 8.1 结构验收

- 模板可从 UI/Agent 加载、保存、复制和导出。
- 工作流没有硬编码 Provider Key 或绝对路径。
- 1 个 Scene 展开为 2 个 image variant task。
- 每个 image task 只生成一个图片资产。
- 每个 image asset 精确关联一个 3 秒 video task。
- Concat 按 variant-01、variant-02 排序。

### 8.2 图像内容验收（两张分别检查）

- 画面总人数严格等于 2，背景没有其他人。
- 教练在左、学员在右。
- 两人均为单板，不出现双板或滑雪杖。
- 教练双脚固定、半蹲、手指向学员前脚固定器。
- 学员仅前脚固定，后脚自由并踩雪，膝盖微屈。
- 板头方向与滑行方向一致。
- 晴天、平缓初级雪道、滑痕/雪粒、虚化雪山和缆车。
- 中景、低机位、35mm、浅景深、自然光、写实电影感。
- 无文字、Logo、水印和明显肢体/装备错误。

如果任一硬约束失败，该图片不得进入 Wan3，先重试图片生成。

### 8.3 视频验收（两段分别检查）

- 每段时长 3 秒，480P，16:9，无音轨。
- 首帧与对应图片一致。
- 全程保持两个人，不新增背景人物。
- 教练只有小幅讲解动作；学员完成一次轻微后脚蹬雪。
- 前脚/后脚固定状态不改变。
- 不切镜、不变成双板、不改变服装或雪板。
- MP4 可播放，ffprobe 可解析。

### 8.4 最终成片

- 两段按变体顺序拼接。
- 目标时长约 6 秒；允许转场造成 ±0.5 秒差异。
- 统一 H.264、yuv420p、480P、目标帧率。
- 最终 Asset 可追溯两段视频、两张图片和 Scene Bundle。

## 9. 测试矩阵

| 层级 | 场景 |
|---|---|
| Unit | variant key、prompt suffix、参数校验、排序 |
| Contract | Qwen/Wan3 payload，无真实调用 |
| Integration Mock | 1 scene → 2 image → 2 video → concat |
| API | 模板创建、Scene Bundle、导出 |
| Frontend | 参数编辑、调用量确认、变体状态、单项重试 |
| Playwright | 加载模板 → Mock 运行 → 查看 2 图/2 视频/成片 |
| External UAT | Qwen 两图、Wan3 两段、FFmpeg 合成 |
| Manual Visual QA | 人数、左右、固定器、姿势、背景、摄影风格 |

## 10. 成本与安全

- 运行前明确显示：2 次图片生成 + 2 次 3 秒视频生成。
- 真实调用需要用户确认，不在自动 CI 中运行。
- 每次 UAT 保存 request_id/task_id，但日志不保存 Key 或签名 URL。
- 失败重试只重试对应 variant，不重复其他成功任务。
- UAT 报告记录模型、参数、耗时、文件哈希和非敏感错误。

## 11. 完成定义

只有同时满足以下条件才算该工作流跑通：

1. Mock E2E 全绿；
2. 两张真实图片均通过内容硬约束；
3. 两段真实 3 秒视频均可播放并保持约束；
4. 最终合成视频可播放且资产血缘完整；
5. WorkflowSpec 与 Scene Bundle 均能导出、重新导入；
6. Provider 可替换，模板无服务密钥和本机路径；
7. 当前环境完整测试、typecheck、build 和浏览器 E2E 全绿；
8. UAT 报告包含 commit、环境、命令、成本和产物哈希。

