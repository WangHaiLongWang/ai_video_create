# Platform Hardening 与 RC 发布计划

> 状态：Active（当前唯一推进主线）
> 日期：2026-10-10
> 校准：2026-10-16
> 上级计划：[DELIVERY-PLAN.md](DELIVERY-PLAN.md)
> 前置专项：[MODULAR-NODE-SEEDREAM-PLAN.md](../archive/MODULAR-NODE-SEEDREAM-PLAN.md)
> 取代关系：取代 [RC-CLOSURE-PLAN.md](../archive/RC-CLOSURE-PLAN.md)（2026-09-21，基线 `cc61b46`），见 §13

## 1. 目标

Phase M3 的模块化、真实 Mock Backend E2E 和 Agent Modify 已完成。下一阶段不再扩展新节点或 Provider，而是将当前系统收敛为可安装、可升级、可回滚、可复现的 `v1.0.0-rc.1`。

```text
功能完成
→ 契约单一来源
→ 数据迁移可追溯
→ 配置/秘密可持久化
→ CI 同 SHA 证据
→ 真实 Provider 受控 UAT
→ RC 演练与发布
```

## 2. 当前基线

> 基线标注日期：2026-10-12。下列数字为 **2026-10-10 实测**（来源 [PROJECT-STATUS.md](../../PROJECT-STATUS.md) §2 与 [platform-audit-2026-10-10.md](../../reports/platform-audit-2026-10-10.md)）；其后**代码未变更**，仍待**同一 SHA 的 CI run 复证**后方可作为 RC 证据。不得把本表数字直接当作发布证明。

| 门禁 | 当前证据（2026-10-10 实测） | 复证要求 |
|---|---|---|
| Frontend unit | 24 files / 414 passed | 待同 SHA CI |
| Frontend type/build | passed；最大 chunk 185.73 kB | 待同 SHA CI |
| Backend non-external | 2181 passed / 8 skipped / 21 deselected / 0 warning | 待同 SHA CI |
| Playwright | 143 passed / 0 skipped / 0 failed | 待同 SHA CI 复证 |
| Module real-Mock E2E | 5 passed，零 route mock | 待同 SHA CI |
| Agent Modify E2E | 3 passed，零 route mock | 待同 SHA CI |
| CI | 三平台 + browser-e2e 配置存在；缺同 SHA run URL | 即 RC-004 关闭对象 |

本机验收与 CI 已统一 Node 22.21.1；runtime preflight 拒绝 Node <22 或 Node >=23。

## 3. Epic H0：可复现工具链（P0，1-2 天）

| ID | 工作量 | 任务 | 验收 | 状态 |
|---|---:|---|---|---|
| HARD-001 | 0.5d | `.nvmrc`/engines/启动检查统一 Node 22；拒绝 Node <22 跑 Playwright | 本机/CI 版本一致 | ✅ 完成：Node 22.21.1、npm 10、engines/preflight/CI 一致 |
| HARD-002 | 0.5d | 建立 Python lock/constraints 或可重复安装报告 | 全新 venv 一次安装成功 | ✅ 完成：`backend/constraints.txt` 固定验证依赖，clean venv 证据已归档 |
| HARD-003 | 0.5d | 清理 Starlette/Pydantic/React act warning | required test 无未审批 warning | ✅ 完成：React act warning 清零；Starlette/AnyIO 上游 warning 精确白名单且其余 warning 视为 error |
| HARD-004 | 0.5d | 固定 unit/E2E worker、文件句柄与 timeout 策略 | 连续运行两次结果一致 | ✅ 完成：cleanup + maxThreads + E2E worker |

## 4. Epic H1：共享契约单一来源（P0，2-3 天）

当前 Node Manifest、ModuleDefinition、WorkflowSpec、Agent Catalog 仍有多份实现。Phase M3 已修复具体漂移，但仍可能再次发生。

| ID | 工作量 | 任务 | 验收 | 状态 |
|---|---:|---|---|---|
| HARD-101 | 1d | 冻结 `schemas/base-node-manifest.json` | 端口 ID/type/cardinality 单一来源 | ✅ 完成：共享 JSON + parity tests |
| HARD-102 | 1d | 冻结 `schemas/module-definition.schema.json` 和 workflow schema | TS/Pydantic roundtrip fixture | ✅ 完成：Draft 2020-12 schema + Pydantic/JSON parity tests |
| HARD-103 | 0.5d | 生成或加载前后端 Catalog，删除手写重复表 | parity test 自动阻断漂移 | ✅ 完成：Node Catalog 共享 manifest，前后端 parity tests |
| HARD-104 | 0.5d | Agent parser/compiler/validator 只消费共享 Catalog | 无私有 port map | ✅ 完成：parser/compiler/validator/API helper 均从 catalog 解析端口 |

## 5. Epic H2：正式数据库迁移（P0，2-3 天）

当前按 SQL 文件启动执行并依赖重复列容错，缺少可靠 migration ledger。

| ID | 工作量 | 任务 | 验收 | 状态 |
|---|---:|---|---|---|
| HARD-201 | 1d | 新增 `schema_migrations`、checksum、事务化 runner | 每个迁移只执行一次 | ✅ 完成：ledger、SHA-256、SAVEPOINT/事务 runner |
| HARD-202 | 0.5d | 现有 001-011 baseline 识别与升级 | 旧库无损升级 | ✅ 完成：legacy adoption + 001-012 顺序升级测试 |
| HARD-203 | 0.5d | 中断、checksum mismatch、损坏备份测试 | 失败不留下半迁移状态 | ✅ 完成：失败回滚、checksum mismatch、重复执行测试 |
| HARD-204 | 0.5d | module_definitions/module_usage/scene drafts 迁移回归 | 重启后数据完整 | ✅ 完成：DB/CRUD/迁移组合回归 64 passed |

## 6. Epic H3：Provider 配置产品化（P1，2-4 天）

Settings API 当前主要修改内存，重启以 `.env` 为准；不满足用户在 Web UI 中长期管理多 Provider 的需求。

| ID | 工作量 | 任务 | 验收 | 状态 |
|---|---:|---|---|---|
| HARD-301 | 1d | ProviderConfig Repository：非秘密配置、capability、启用状态 | 重启恢复 | ✅ 完成：013 migration + repository/API + restart persistence |
| HARD-302 | 1d | Secret reference 接 AES-GCM 存储；GET 永不回显 | 轮换和脱敏测试 | ✅ 完成：encrypted secret namespace、脱敏 GET、轮换测试 |
| HARD-303 | 1d | 多 Provider CRUD、默认选择、模型发现、测试连接 | 同 capability 多配置可切换 | ✅ 完成：CRUD/default/models/test endpoints，15 targeted passed |
| HARD-304 | 0.5d | Workflow/Module 只保存 provider config ID | 不保存 Key/Base URL秘密 | ✅ 完成：providerConfigId 引用 + workflow/module sanitizer |

## 7. Epic H4：Agent 与兼容层收口（P1，1-2 天）

| ID | 工作量 | 任务 | 验收 | 状态 |
|---|---:|---|---|---|
| HARD-401 | 0.5d | 冻结 Agent v2；为 v1 增加弃用响应、迁移窗口 | v1/v2 行为明确 | ✅ 完成：v1 endpoints 标记 deprecated，v2 为主契约 |
| HARD-402 | 0.5d | image-only 终点产品决策：通用 AssetOutput 或明确终端节点 | 不依赖无 output 节点的隐式语义 | ✅ 完成：output 显式提供 optional `video`/`asset` sink，image-only 连接 `output.asset` |
| HARD-403 | 0.5d | Modify/Apply 审计记录 prompt hash、module diff、repair count | 可追溯且脱敏 | ✅ 完成：012 migration、API、前端 Trace Panel/tests |
| HARD-404 | 0.5d | 限制节点/scene/variant/预计费用 | 超限在 apply 前阻止 | ✅ 完成：Agent preview/apply + execution start 前置门禁与资源限额测试 |

## 8. Epic H5：CI 与真实 Provider 验收（P0/P1，2-3 天）

| ID | 工作量 | 任务 | 验收 | 状态 |
|---|---:|---|---|---|
| HARD-501 | 0.5d | 触发同 SHA 三平台 CI + browser-e2e | required checks 全绿 | ⛔ External：workflow 已修复并本地全绿；需 push 当前提交后取得 Actions URL |
| HARD-502 | 0.5d | 归档 JUnit、Playwright report/trace、安全报告、build | 报告记录 Actions URL/SHA | 🔶 本地完成：CI 已上传 JUnit/build/Playwright/security；远端 artifact URL 依赖 HARD-501 |
| HARD-503 | 0.5d | MiMo 当前 commit smoke | structured intent 成功 | ✅ 完成：`78a99ac` 实测成功，8.20 s |
| HARD-504 | 0.5d | Qwen Image + Wan3 最小真实链路 | 1 scene/1 variant/最低时长 | ✅ 完成：`78a99ac` PNG + 2s/480P MP4，哈希/job ID/估算费用归档 |
| HARD-505 | 外部 | 激活 Seedream/Seedance 或配置 Endpoint | Doubao UAT 不再 404 | ⛔ External：代码/契约/Mock 已完成，账号模型未激活 |
| HARD-506 | 0.5d | Provider 失败/429/timeout/cancel 演练 | 不产生假成功资产 | ✅ 完成：失败/429/timeout/cancel drills，非 Mock 禁止 synthetic success |

真实 Provider job 必须是 manual/nightly，不作为普通 PR 默认门禁；每次设置调用量上限和产物清理策略。

## 9. Epic H6：发布与运维（P0，1-2 天）

| ID | 工作量 | 任务 | 验收 | 状态 |
|---|---:|---|---|---|
| HARD-601 | 0.5d | 统一 package/backend/version/tag | UI/API/tag 同版本 | 🔶 代码完成：`v1.0.0-rc.1` 单一版本源；tag 必须等待同 SHA CI |
| HARD-602 | 0.5d | 更新 CHANGELOG 日期、测试数字、Known Issues | 与当前 SHA 一致 | ✅ 完成：CHANGELOG/版本/已知问题一致 |
| HARD-603 | 0.5d | 安装、升级、回滚、数据库备份恢复演练 | 新机器按文档成功 | ✅ 完成：在线备份/校验/恢复前备份，文档与自动测试通过 |
| HARD-604 | 0.5d | RC checklist、签名/哈希/依赖清单 | artifact 可验证 | 🔶 本地完成：checklist/manifest/SHA-256/preflight；签发 tag 等待 HARD-501 |

## 10. HARD 与发布阻断 / DoD 映射

发布阻断编号以 [PROJECT-STATUS.md](../../PROJECT-STATUS.md) §6 为准。RC-001/002/003 已关闭，不在此表；剩余阻断由 HARD-5xx 承接，其余 Epic 支撑 DoD。

### 10.1 剩余发布阻断

| 发布阻断（PROJECT-STATUS §6） | 主承接工单 | 支撑工单 | 关闭标准摘要 |
|---|---|---|---|
| RC-004 同一 commit CI 证据（P0） | HARD-501、HARD-502 | HARD-001、HARD-003、HARD-004 | 三平台 required checks + browser-e2e run URL/SHA/artifact |
| RC-008 真实 Qwen/Wan3 当前证据（P1） | HARD-504 | HARD-506 | 当前 commit 受控 UAT（1 scene/1 variant/最低时长），或明确移出 RC 范围 |
| RC-007 Doubao 模型未激活（P1，外部阻断） | HARD-505 | — | 激活或配置 Endpoint 后 image/video/workflow UAT；不计入工程工期 |

### 10.2 DoD 条目

| DoD（§12） | 承接工单 |
|---|---|
| 1 工具链一致（Node 22 / Python 3.12） | HARD-001、HARD-002 |
| 2 Schema 单一来源 | HARD-101、HARD-102、HARD-103、HARD-104 |
| 3 migration ledger/恢复/升级证据 | HARD-201、HARD-202、HARD-203、HARD-204 |
| 4 Provider 设置重启恢复、Key 不回显 | HARD-301、HARD-302、HARD-303、HARD-304 |
| 5 Agent v2 冻结、v1 弃用策略 | HARD-401、HARD-402、HARD-403、HARD-404 |
| 6 同 SHA required checks 全绿 | HARD-501、HARD-502、HARD-503（并受 HARD-003/004 稳定性支撑） |
| 7 MiMo/Qwen/Wan3 最小 UAT、Doubao 状态明确 | HARD-503、HARD-504、HARD-505、HARD-506 |
| 8 版本/CHANGELOG/安装升级回滚文档一致 | HARD-601、HARD-602、HARD-603 |
| 9 tag 只指向已验证 SHA | HARD-604（依赖 §10.1 全部关闭） |

## 11. 建议排期

排期与 §12 DoD 对齐；DoD 勾选框在全部证据归档前保持未勾。

```text
Sprint H1（3-4 天）
  H0 工具链 + H1 共享契约 + H2 migration ledger
  → 覆盖 DoD 1/2/3

Sprint H2（3-4 天）
  H3 Provider 持久化 + H4 Agent兼容层
  → 覆盖 DoD 4/5

Sprint H3（2-3 天）
  H5 CI/UAT + H6 Release drill
  → 覆盖 DoD 6/7/8/9；关闭 RC-004/RC-008（RC-007 为外部等待，不计入工期）
```

按 2026-10-15 已完成 HARD-004/101/403 和实测 HARD-503/504 后重估：两人并行约 5-8 个工作日；单人约 9-13 个工作日。外部模型激活等待不计入工程工期。

### 11.1 下一 Sprint 可直接领取

| 顺序 | 工单 | Owner 建议 | 出口 |
|---:|---|---|---|
| 1 | HARD-001/002/003 | DevOps + QA | Node 22、Python lock、required test 无 warning |
| 2 | HARD-102/103/104 | Architecture + Fullstack | Module/Workflow/Agent 共享 Schema |
| 3 | HARD-201/202 | Backend | migration ledger + 001-012 baseline |
| 4 | HARD-203/204 | Backend + QA | 中断恢复、checksum、旧库数据完整 |
| 5 | HARD-301/302 | Backend/Security | Provider Repository + secret reference |
| 6 | HARD-501/502 | DevOps/QA | 当前 SHA CI run URL 和 artifacts |

依赖顺序：HARD-001/002 → HARD-501/502；HARD-102/103 → HARD-201 baseline fixture；Provider 持久化可与 migration runner 并行设计，但落库迁移必须走 HARD-201 runner。

## 12. Definition of Done

- [x] Node 22/Python 3.12 的本机和 CI 工具链一致。
- [x] 前后端 Node/Module/Workflow Schema 共享同一来源。
- [x] 数据库 migration 有 ledger、checksum、中断恢复和旧库升级证据。
- [x] Provider 设置重启恢复，Key 不回显且可轮换。
- [x] Agent v2 契约冻结，v1 有明确弃用策略。
- [ ] 同一 SHA 的三平台、browser-e2e、security、media required checks 全绿。
- [x] MiMo/Qwen/Wan3 最终实现 commit 最小 UAT 通过，Doubao 状态明确。
- [x] 版本、CHANGELOG、Known Issues、安装/升级/回滚文档一致。
- [ ] `v1.0.0-rc.1` tag 只指向已验证 SHA。

## 13. 与 RC-CLOSURE-PLAN 的关系

[RC-CLOSURE-PLAN.md](../archive/RC-CLOSURE-PLAN.md)（2026-09-21，基线 `cc61b46`）已 **Superseded by PLATFORM-HARDENING-PLAN（2026-10-12）** 并归档。取代边界如下：

1. **推进主线**：Epic H0-H6（HARD-xxx）是当前唯一推进主线；RC-CLOSURE-PLAN 的工单表、基线数字和 Day 1-4 执行顺序均为历史快照，不再用于领取任务或判断完成度。
2. **发布阻断登记**：剩余未关闭项以 [PROJECT-STATUS.md](../../PROJECT-STATUS.md) §6 为准——RC-001/002/003/008 已关闭；RC-004 为远端同 SHA 证据、RC-007 为账号激活，两项均已推进到外部执行边界。工程承接见 §10（HARD-501/502/505）。
3. **编号说明**：RC-CLOSURE-PLAN §3 的 RC-001A/RC-002… 与 PROJECT-STATUS §6 的 RC-001… 并非同一套编号，勿混用；当前有效发布阻断 ID 只认 PROJECT-STATUS §6。
4. **处理方式**：采用「原地标注 Superseded + 历史快照」而非「迁 ID 后改归档指引」。理由：未关闭项已在 PROJECT-STATUS §6 登记、由本计划 HARD-5xx 承接，再迁移一次只会制造第三处跟踪或 ID 冲突；原地标注保留 2026-09-21 决策上下文，符合增量校准、不删历史的约束。

## 14. 明确不做

- 新增第三方 Provider 或新节点类型。
- 任意脚本/Docker 插件运行时。
- 专业时间线、音轨、字幕和协作功能。
- 在普通 PR 中执行付费生成。
