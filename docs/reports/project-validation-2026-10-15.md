# 项目验证与平台硬化检查点 2026-10-15

> Commit：`ef8ad99`
> 环境：Windows / 当前 shell Node 16.14.2 / Python 3.12.3

## 结论

功能主链和 Phase M3 已完成，Platform Hardening 已开始交付。当前不再缺模块化核心功能，发布阻断集中于工具链一致、Schema/迁移/Provider 配置治理、同 SHA CI 证据和 RC 发布演练。

## 本轮复测

| 门禁 | 结果 |
|---|---|
| Frontend Vitest | 22 files / 387 passed |
| TypeScript | passed |
| Vite build | passed；index 138.51 kB，最大 chunk 185.73 kB |
| Backend 功能专项 | 153 passed / 1 Starlette warning |
| Shared Node Catalog + Agent Trace | 119 passed / 1 Starlette warning |

Playwright 未在本轮默认 shell执行：当前 Node 16，低于 Playwright Node 20+ 要求。历史当前功能基线为 142 passed / 1 skipped / 0 failed，仍待 `ef8ad99` 同 SHA CI 复证。

## Platform Hardening 进度

| 工单 | 状态 | 证据 |
|---|---|---|
| HARD-004 | Done | cleanup/maxThreads/E2E worker 已固定 |
| HARD-101 | Done | `schemas/base-node-manifest.json` + TS/Python loader/parity tests |
| HARD-103 | Partial | Base Node Catalog 已切换；Module/Workflow Schema 尚未统一 |
| HARD-104 | Partial | Agent tools 使用共享 Catalog；parser 私有 port 常量待清理 |
| HARD-403 | Done | 012 migration、trace service/API、Frontend Trace Panel/tests |
| HARD-503 | 功能通过 | MiMo 真实文本调用成功，待正式报告归档 |
| HARD-504 | 功能通过 | Qwen 图片 + Wan3 视频成功，待正式报告归档 |

## 真实链路证据

2026-10-12 执行 `python scripts/smoke_real_chain.py chain`：

| 步骤 | 结果 | 耗时 | 产物 |
|---|---|---:|---|
| MiMo `mimo-v2.5-pro` | passed | 6.23s | image prompt |
| Qwen Image 3.0 | passed | 72.43s | 1280×720 PNG / 1,471,278 bytes |
| Wan3 Video | passed | 44.29s | 2s / 480P MP4 / 2,242,752 bytes |

本地文件：

```text
data/uat/20261012-112731/scene-001-variant-01.png
data/uat/20261012-112731/scene-001-variant-01.mp4
```

发现配置缺陷：`.env` 的 MiMo `max_completion_tokens` 超过模型上限时会返回 HTTP 400；smoke 脚本只做了临时钳位。应由 HARD-301/303/506 在配置保存或 Provider 构造阶段校验，而不是依赖 smoke 绕过。

## 下一步

执行 [`PLATFORM-HARDENING-PLAN.md`](../plans/active/PLATFORM-HARDENING-PLAN.md)：

1. HARD-001/002/003 工具链、lock 与 warning；
2. HARD-102/103/104 Module/Workflow/Agent Schema 单一来源；
3. HARD-201～204 migration ledger；
4. HARD-301～304 Provider 持久化与参数校验；
5. HARD-501/502 同 SHA CI 证据；
6. HARD-601～604 RC 发布演练。
