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
