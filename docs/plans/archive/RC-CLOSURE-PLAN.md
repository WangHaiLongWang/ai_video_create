# v1.0.0-rc.1 收敛计划

> **已被取代说明（2026-10-12）**：本计划已由 [PLATFORM-HARDENING-PLAN.md](../active/PLATFORM-HARDENING-PLAN.md) 取代，不再是推进主线。当前发布阻断与关闭标准以 [PROJECT-STATUS.md](../../PROJECT-STATUS.md) §6 为准；以下正文仅作**历史快照**，不用于领取任务或判断完成度。

> 状态：Superseded by PLATFORM-HARDENING-PLAN（2026-10-12）
> 日期：2026-09-21（历史快照）
> 基线：`cc61b46`（历史快照）
> 上级计划：[DELIVERY-PLAN.md](../active/DELIVERY-PLAN.md)
> 事实基线：[PROJECT-STATUS.md](../../PROJECT-STATUS.md)
> 取代计划：[PLATFORM-HARDENING-PLAN.md](../active/PLATFORM-HARDENING-PLAN.md)

**处理方式说明**：采用「原地标注 Superseded + 历史快照」，而非把 RC-004/007/008 迁入 HARD-5xx 后改写本文件为归档指引。理由：(1) 剩余未关闭的发布阻断已在 PROJECT-STATUS §6 权威登记，工程承接已在 PLATFORM-HARDENING-PLAN HARD-501/502/504/505，再迁移一次只会制造第三处跟踪；(2) 本文件 §3 的 RC-001A/RC-002… 编号与 PROJECT-STATUS §6 的 RC-001… 并非同一套体系，迁移易混淆；(3) 原地标注完整保留 2026-09-21 决策上下文，符合不删历史、增量校准的约束。

## 1. 目标与非目标

目标是在不扩展新业务范围的前提下，将当前内部 Beta 收敛为可追溯、可复现的 `v1.0.0-rc.1`。

本计划不新增节点类型、不新增 Provider、不扩展时间线功能。Doubao 保持可选 Provider，模型激活不阻断 Qwen+Wan3 的 RC 主路径。

## 2. 当前基线（历史快照，2026-09-21）

> 以下数字为 2026-09-21 时期记录，已过期。当前基线以 [PROJECT-STATUS.md](../../PROJECT-STATUS.md) §2（2026-10-10）为准：Frontend 387 passed、Playwright 142 passed / 1 skipped / 0 failed、Backend 干净 venv 2123 passed / 8 skipped / 0 failed。

```text
Frontend unit:     295 passed
Frontend build:    passed
Chromium E2E:      132 passed / 2 failed / 1 skipped
Backend full:      1561 passed / 0 failed / 29 skipped (all green)
Backend acceptance: 170 passed / 0 failed
Provider tests:    44 passed
```

## 3. P0 工作分解（历史快照，2026-09-21）

| ID | Owner | 工作量 | 交付 | 验收 | 依赖 |
|---|---|---:|---|---|---|
| RC-001A | Backend | 0.5d | requirements 增加 cryptography 并锁定 Pillow | 新 venv 可导入 PIL/AESGCM | 无 |
| RC-001B | QA | 0.5d | 干净环境完整 pytest | 全量收集，无意外 skip | 001A |
| RC-002 | Backend | 1d | 修复/迁移 Agent v1 acceptance | 3 个失败转绿；v1 行为有弃用说明 | 001A |
| RC-003A | Frontend | 0.25d | pane click locator/交互修复 | deselect E2E 通过 | 无 |
| RC-003B | Frontend | 0.5d | 第二节点拖拽稳定性修复 | 两节点独立拖拽 + Undo 通过 | 无 |
| RC-003C | Fullstack | 0.5d | 启用 Scene JSON roundtrip | 不再 skip，导入导出等价 | backend 可启动 |
| RC-004 | DevOps/QA | 1d | 新增 Playwright CI job | 启动 Mock backend+Vite，Chromium 全绿 | 001-003 |
| RC-005 | DevOps | 0.5d | 移除 integration `|| true` | 必选集失败阻断，external 独立 job | 001B |
| RC-006 | QA | 0.5d | 同一 commit 三平台验证 | Actions URL、SHA、artifact 入报告 | 004/005 |

## 4. 前端验收矩阵

### React Flow

- 侧栏点击和拖入创建节点；缩放/平移后的落点正确。
- 单节点、多节点移动；一次拖动产生一个历史事务。
- 合法拖线生成 Edge；类型、自环、重复、环、基数错误均拒绝并显示原因。
- 删除动态端口同步删除关联边，一个 Undo 完整恢复。
- Edge label/mode/order/reconnect 保存刷新不丢失。
- viewport、selection、copy/paste 和键盘删除行为稳定。

### Agent/Scene/执行

- Prompt → v2 preview → apply → save → Mock run。
- Scene Draft 保存、刷新和后端重启后恢复。
- JSON export → import 保持 scene_id、顺序、锁定状态和 prompts。
- TaskPreview 展示图片/视频；失败 item 可单项 retry。
- 非 Mock 请求失败时 UI 展示 Provider error，不伪造成功资产。

## 5. CI 设计

```text
backend-unit (3 OS)
  requirements install → import smoke → pytest non-external

frontend-unit (3 OS)
  npm ci → test → typecheck → build

browser-e2e (Linux)
  install Chromium
  start FastAPI in Mock mode
  wait /api/health
  start Vite
  playwright test --project=chromium
  upload report/trace/screenshot

media-integration (Linux)
  install/resolve FFmpeg
  run deterministic FFmpeg integration

external-provider (manual/nightly)
  explicit secrets + cost limits
  never required for ordinary PR
```

禁止使用 `|| true`、吞异常或仅输出 warning 继续通过。外部服务不可用应使用明确 marker 和单独 job，而不是让核心门禁失真。

## 6. Definition of Done（历史快照，2026-09-21）

> 勾选状态仅反映 2026-09-21 时期判断；当前 DoD 以 [PLATFORM-HARDENING-PLAN.md](../active/PLATFORM-HARDENING-PLAN.md) §12 为准。

- [x] requirements 可在全新 Python 3.12 venv 安装。
- [x] backend full non-external suite 全绿。
- [ ] frontend 295+ unit tests、typecheck、build 全绿。
- [ ] Chromium 135 项不含无审批 skip，全部通过。
- [x] CI 不包含关键路径 `|| true`。
- [ ] 同一 SHA 的 Windows/macOS/Linux required checks 全绿。
- [ ] Playwright report、JUnit、安全报告和 build artifact 可下载。
- [x] CHANGELOG、安装、升级、回滚和已知问题已更新。
- [ ] `v1.0.0-rc.1` tag 指向已验证 SHA。

## 7. 风险与回滚

- Agent v1 修复不得破坏 v2；优先增加兼容适配或明确 410/弃用窗口。
- E2E 修复必须先判断产品 bug 或测试 bug，不得通过降低断言掩盖问题。
- migration 只允许向前修复；发布演练前备份测试数据库。
- Provider UAT 使用单场景、单变体和最低可接受时长，设置显式成本上限。
- RC 回滚保留上一版本代码和数据库备份，生成资产不自动删除。

## 8. 建议执行顺序（历史快照，2026-09-21）

> 以下 Day 1-4 顺序已被 PLATFORM-HARDENING-PLAN §11 排期取代。

```text
Day 1: RC-001A + RC-003A/B
Day 2: RC-001B + RC-002 + RC-003C
Day 3: RC-004 + RC-005
Day 4: RC-006 + release docs/tag drill
```

任何 P0 未关闭时，不创建 RC tag。
