# MiMo → Qwen Image → Wan3 真实链路 UAT

> 执行日期：2026-10-12 11:27（Asia/Shanghai）
> 脚本：[`scripts/smoke_real_chain.py`](../../scripts/smoke_real_chain.py)
> 范围：1 次文本结构化、1 次图片生成、1 次视频生成；不代表批量生产 SLA。

## 结果

| 阶段 | 模型/参数 | 结果 | 耗时 |
|---|---|---|---:|
| LLM | MiMo（OpenAI-compatible） | structured intent 成功 | 6.23 s |
| 图片 | Qwen-Image-3.0，1280×720 PNG | 成功，可读取 | 72.43 s |
| 视频 | Wan3，480P，2 s MP4 | 成功，可读取 | 44.29 s |

产物位于 `data/uat/20261012-112731/`：

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| `scene-001-variant-01.png` | 1,471,278 | `E9F38E6D638643BFB3AF7932B809F28F7870FB6AC2E58CBAA2DA15BD144BB7C3` |
| `scene-001-variant-01.mp4` | 2,242,752 | `397210E6869EADA8F1BDFC79F5A65C4BAFB2F4FFA553AF4A848EE9D159BFB849` |

## 复现与边界

```powershell
python scripts/smoke_real_chain.py chain
```

本次报告是 2026-10-12 的真实调用记录，执行时的工作树提交未在日志中锁定，因此不能直接作为当前提交的 RC-008 证据；当前提交必须重新执行同样的受控链路并补充 commit SHA、环境摘要、供应商 job ID（脱敏）和实际费用。脚本会将 MiMo `max_tokens` 钳制到不超过 8192，避免 `.env` 中超过供应商 131072 上限的配置导致 400。

成本未在执行日志中记录；重新验收时必须从供应商账单或响应元数据补录，禁止估算后标记为已归档。

## 最终实现提交复证（2026-10-16）

> 实现提交：`78a99ac5cee2eecb2956cd61c00d72056d7cc842`
> 执行目录：`data/uat/20261016-095952/`（本地忽略，不提交媒体二进制）

| 阶段 | 结果 | 耗时/规格 |
|---|---|---|
| MiMo `mimo-v2.5-pro` | ✅ structured prompt | 8.20 s |
| Qwen Image 3.0 | ✅ PNG / 1,220,245 bytes | 88.39 s |
| Wan3 | ✅ MP4 / 1,807,429 bytes | 58.89 s；2 s / 480P |

| 文件 | SHA-256 |
|---|---|
| `scene-001-variant-01.png` | `E13950DB5D71A11221C7505709AF395378BF038BD5077C5E083C4F5FF697DDBC` |
| `scene-001-variant-01.mp4` | `5A792E8CF8D193A515BAF856B39B1BBE98B02D1F60992AA8AF431E46AFE572E5` |

Wan3 external job ID：`36c99675-…-6101`（报告仅保留脱敏形式）。按系统配置的单位成本估算，本次 1 次 storyboard + 1 次 image + 1 次 video 为 **USD 0.26**；这是门禁估算，不冒充供应商实际账单。供应商响应未返回实扣金额，财务核账应以控制台账单为准。
