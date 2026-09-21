# 项目门禁审计报告 2026-09-21

> Commit：`cc61b46`
> 工作区：审计前 clean；本报告和 docs 更新为本轮变更
> 环境：Windows / Node 22.21.1 / npm 10.9.4 / Python 3.12.3

## 结果摘要

| 门禁 | 结果 |
|---|---|
| Frontend Vitest | 17 files / 295 passed |
| TypeScript | passed |
| Vite build | passed；main 94.99 kB，最大 chunk 171.08 kB |
| Chromium Playwright | 132 passed / 2 failed / 1 skipped，135 total |
| Backend full collection | failed；缺 Pillow、cryptography |
| Backend runnable subset | 1521 passed / 3 failed / 20 skipped |
| Provider tests | 44 passed |

## Chromium 失败

1. Canvas background deselect：测试点击 viewport，被 pane 拦截。
2. Multiple node drag：第二个节点纵向位移断言为 0。
3. Scene JSON roundtrip：用例被 skip。

完整 HTML 报告位于 [`frontend/playwright-report/index.html`](../../frontend/playwright-report/index.html)。该套件未启动 FastAPI，运行日志存在 API proxy `ECONNREFUSED`，因此结果仅作为前端浏览器证据。

## Backend 阻断

- 当前 venv 未安装 requirements 已声明的 Pillow。
- `secret_encryption.py` 使用 AESGCM，但 requirements 未声明 cryptography。
- 可运行套件中的 3 个失败均来自 `tests/acceptance/test_e2e.py` 的旧 Agent v1 Mock 流程。

## CI 审计

- Node 20、Python 3.12 和三平台 matrix 已配置。
- 没有 Playwright CI job。
- integration 两处使用 `|| true`，失败不会阻断。
- 只有 workflow 配置，没有同一 SHA 的 Actions run 证据。

## 判定

项目处于内部 Beta / RC 前收敛，不能标记为 RC。关闭标准和工单见 [`RC-CLOSURE-PLAN.md`](../plans/active/RC-CLOSURE-PLAN.md)。
