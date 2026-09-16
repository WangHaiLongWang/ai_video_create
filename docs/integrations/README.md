# Provider 集成索引

| 能力 | 默认 Provider | 文档 | 验证状态 |
|---|---|---|---|
| 文本/分镜 | Xiaomi MiMo `mimo-v2.5-pro` | [MiMo](mimo-v2.5-pro.md) | 真实 Chat Completions 通过 |
| 文生图 | Qwen Image `qwen-image-3.0` | [Qwen Image](qwen-image-3.0.md) | 真实 1280×720 生图通过 |
| 图生视频 | Wan3 `wan3.0-video` | [Wan3](wan3-video.md) | 历史 UAT 报告通过；当前 venv 待复现 |
| 本地生成 | ComfyUI | [Wan3/ComfyUI 边界](wan3-video.md#comfyui-配置) | T2I 未实测；I2V workflow 为占位 |

## 维护规则

- 只记录官方 endpoint、参数、限制和项目映射。
- Key 始终为空白示例，不写真实密钥。
- 实际成功率、测试数量和缺陷写入 `../PROJECT-STATUS.md`。
- 特定运行的原始证据写入 `../reports/`。
- 新 Provider 必须先定义 capability 和 Contract Test，再加入设置 UI。

