# Platform Hardening 基线审计 2026-10-10

> Commit：`44d2227`
> 环境：Windows / 默认 shell Node 16.14.2 / npm 8.5.0 / Python 3.12.3

## 结论

Phase M3 功能已完成，项目应停止扩展模块功能，转入共享契约、迁移、Provider 配置、CI/UAT 和 RC 发布治理。

## 本轮复测

| 门禁 | 结果 |
|---|---|
| Frontend Vitest | 22 files / 387 passed |
| TypeScript | passed |
| Vite build | passed；index 138.51 kB，最大 chunk 185.73 kB |
| Backend 当前专项 | 153 passed / 1 Starlette deprecation warning |

历史同分支证据：Playwright 142 passed / 1 skipped，干净 venv non-external backend 2123 passed / 8 skipped。该历史结果必须由同一 SHA CI run 取代后才能作为 RC 证据。

## 发现

1. 本机默认 shell 仍解析到 Node 16，虽然 unit/build 可运行，但 Playwright 要求 Node 20+。
2. Node/Module/Agent Catalog 仍存在多份手写定义，未来漂移风险高。
3. 数据库迁移缺 `schema_migrations` ledger/checksum。
4. Provider Settings 主要是内存状态，重启回退 `.env`。
5. CHANGELOG 的 RC 日期和旧测试数字已过期。
6. React unit tests 仍输出 act warning；Starlette TestClient 有 deprecation warning。
7. Doubao 模型仍未激活，真实 Seedream/Seedance UAT blocked。

## 下一步

执行 [`PLATFORM-HARDENING-PLAN.md`](../plans/active/PLATFORM-HARDENING-PLAN.md)，优先级：工具链 → 共享契约 → migration ledger → Provider 持久化 → CI/UAT → RC release drill。
