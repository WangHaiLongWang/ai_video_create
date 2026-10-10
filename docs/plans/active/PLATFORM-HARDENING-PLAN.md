# Platform Hardening 与 RC 发布计划

> 状态：Active
> 日期：2026-10-10
> 上级计划：[DELIVERY-PLAN.md](DELIVERY-PLAN.md)
> 前置专项：[MODULAR-NODE-SEEDREAM-PLAN.md](MODULAR-NODE-SEEDREAM-PLAN.md)

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

| 门禁 | 当前证据 |
|---|---|
| Frontend unit | 22 files / 387 passed |
| Frontend type/build | passed；最大 chunk 185.73 kB |
| Backend 当前专项 | 153 passed / 1 deprecation warning |
| Backend clean venv non-external | 历史当前分支证据：2123 passed / 8 skipped / 0 failed |
| Playwright | 历史当前分支证据：142 passed / 1 skipped / 0 failed |
| Module real-Mock E2E | 5 passed，零 route mock |
| Agent Modify E2E | 3 passed，零 route mock |
| CI | 三平台 + browser-e2e 配置存在；缺同 SHA run URL |

本机默认 shell 当前解析到 Node 16.14.2；Playwright 需要 Node 20+。开发和 CI 必须统一到 Node 22 LTS 或至少 Node 20。

## 3. Epic H0：可复现工具链（P0，1-2 天）

| ID | 工作量 | 任务 | 验收 |
|---|---:|---|---|
| HARD-001 | 0.5d | `.nvmrc`/engines/启动检查统一 Node 22；拒绝 Node <20 跑 Playwright | 本机/CI 版本一致 |
| HARD-002 | 0.5d | 建立 Python lock/constraints 或可重复安装报告 | 全新 venv 一次安装成功 |
| HARD-003 | 0.5d | 清理 Starlette/Pydantic/React act warning | required test 无未审批 warning |
| HARD-004 | 0.5d | 固定 unit/E2E worker、文件句柄与 timeout 策略 | 连续运行两次结果一致 |

## 4. Epic H1：共享契约单一来源（P0，2-3 天）

当前 Node Manifest、ModuleDefinition、WorkflowSpec、Agent Catalog 仍有多份实现。Phase M3 已修复具体漂移，但仍可能再次发生。

| ID | 工作量 | 任务 | 验收 |
|---|---:|---|---|
| HARD-101 | 1d | 冻结 `schemas/base-node-manifest.json` | 端口 ID/type/cardinality 单一来源 |
| HARD-102 | 1d | 冻结 `schemas/module-definition.schema.json` 和 workflow schema | TS/Pydantic roundtrip fixture |
| HARD-103 | 0.5d | 生成或加载前后端 Catalog，删除手写重复表 | parity test 自动阻断漂移 |
| HARD-104 | 0.5d | Agent parser/compiler/validator 只消费共享 Catalog | 无私有 port map |

## 5. Epic H2：正式数据库迁移（P0，2-3 天）

当前按 SQL 文件启动执行并依赖重复列容错，缺少可靠 migration ledger。

| ID | 工作量 | 任务 | 验收 |
|---|---:|---|---|
| HARD-201 | 1d | 新增 `schema_migrations`、checksum、事务化 runner | 每个迁移只执行一次 |
| HARD-202 | 0.5d | 现有 001-011 baseline 识别与升级 | 旧库无损升级 |
| HARD-203 | 0.5d | 中断、checksum mismatch、损坏备份测试 | 失败不留下半迁移状态 |
| HARD-204 | 0.5d | module_definitions/module_usage/scene drafts 迁移回归 | 重启后数据完整 |

## 6. Epic H3：Provider 配置产品化（P1，2-4 天）

Settings API 当前主要修改内存，重启以 `.env` 为准；不满足用户在 Web UI 中长期管理多 Provider 的需求。

| ID | 工作量 | 任务 | 验收 |
|---|---:|---|---|
| HARD-301 | 1d | ProviderConfig Repository：非秘密配置、capability、启用状态 | 重启恢复 |
| HARD-302 | 1d | Secret reference 接 AES-GCM 存储；GET 永不回显 | 轮换和脱敏测试 |
| HARD-303 | 1d | 多 Provider CRUD、默认选择、模型发现、测试连接 | 同 capability 多配置可切换 |
| HARD-304 | 0.5d | Workflow/Module 只保存 provider config ID | 不保存 Key/Base URL秘密 |

## 7. Epic H4：Agent 与兼容层收口（P1，1-2 天）

| ID | 工作量 | 任务 | 验收 |
|---|---:|---|---|
| HARD-401 | 0.5d | 冻结 Agent v2；为 v1 增加弃用响应、迁移窗口 | v1/v2 行为明确 |
| HARD-402 | 0.5d | image-only 终点产品决策：通用 AssetOutput 或明确终端节点 | 不依赖无 output 节点的隐式语义 |
| HARD-403 | 0.5d | Modify/Apply 审计记录 prompt hash、module diff、repair count | 可追溯且脱敏 |
| HARD-404 | 0.5d | 限制节点/scene/variant/预计费用 | 超限在 apply 前阻止 |

## 8. Epic H5：CI 与真实 Provider 验收（P0/P1，2-3 天）

| ID | 工作量 | 任务 | 验收 |
|---|---:|---|---|
| HARD-501 | 0.5d | 触发同 SHA 三平台 CI + browser-e2e | required checks 全绿 |
| HARD-502 | 0.5d | 归档 JUnit、Playwright report/trace、安全报告、build | 报告记录 Actions URL/SHA |
| HARD-503 | 0.5d | MiMo 当前 commit smoke | structured intent 成功 |
| HARD-504 | 0.5d | Qwen Image + Wan3 最小真实链路 | 1 scene/1 variant/最低时长 |
| HARD-505 | 外部 | 激活 Seedream/Seedance 或配置 Endpoint | Doubao UAT 不再 404 |
| HARD-506 | 0.5d | Provider 失败/429/timeout/cancel 演练 | 不产生假成功资产 |

真实 Provider job 必须是 manual/nightly，不作为普通 PR 默认门禁；每次设置调用量上限和产物清理策略。

## 9. Epic H6：发布与运维（P0，1-2 天）

| ID | 工作量 | 任务 | 验收 |
|---|---:|---|---|
| HARD-601 | 0.5d | 统一 package/backend/version/tag | UI/API/tag 同版本 |
| HARD-602 | 0.5d | 更新 CHANGELOG 日期、测试数字、Known Issues | 与当前 SHA 一致 |
| HARD-603 | 0.5d | 安装、升级、回滚、数据库备份恢复演练 | 新机器按文档成功 |
| HARD-604 | 0.5d | RC checklist、签名/哈希/依赖清单 | artifact 可验证 |

## 10. 建议排期

```text
Sprint H1（3-4 天）
  H0 工具链 + H1 共享契约 + H2 migration ledger

Sprint H2（3-4 天）
  H3 Provider 持久化 + H4 Agent兼容层

Sprint H3（2-3 天）
  H5 CI/UAT + H6 Release drill
```

两人并行约 7-10 个工作日；单人约 12-16 个工作日。外部模型激活等待不计入工程工期。

## 11. Definition of Done

- [ ] Node 22/Python 3.12 的本机和 CI 工具链一致。
- [ ] 前后端 Node/Module/Workflow Schema 共享同一来源。
- [ ] 数据库 migration 有 ledger、checksum、中断恢复和旧库升级证据。
- [ ] Provider 设置重启恢复，Key 不回显且可轮换。
- [ ] Agent v2 契约冻结，v1 有明确弃用策略。
- [ ] 同一 SHA 的三平台、browser-e2e、security、media required checks 全绿。
- [ ] MiMo/Qwen/Wan3 当前 commit 最小 UAT 通过，Doubao 状态明确。
- [ ] 版本、CHANGELOG、Known Issues、安装/升级/回滚文档一致。
- [ ] `v1.0.0-rc.1` tag 只指向已验证 SHA。

## 12. 明确不做

- 新增第三方 Provider 或新节点类型。
- 任意脚本/Docker 插件运行时。
- 专业时间线、音轨、字幕和协作功能。
- 在普通 PR 中执行付费生成。
