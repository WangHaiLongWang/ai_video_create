# 验收报告索引

| 报告 | 结论 | 当前可复现性 |
|---|---|---|
| [Wan3 UAT](wan3-uat.md) | 报告记录 480P/2s 真实任务成功 | 当前 venv 缺 Pillow，完整套件收集失败 |
| [FFmpeg 集成](ffmpeg-integration.md) | 报告记录 normalize/concat/probe 19/19 | 当前配置找不到 FFmpeg，7 项集成测试失败 |
| [Doubao UAT 2026-09-21](doubao-uat-2026-09-21.md) | Key/目录通过，媒体模型未激活 | 激活模型或配置 Endpoint ID 后复测 |
| [项目门禁审计 2026-09-21](project-audit-2026-09-21.md) | Frontend 295 通过；Chromium 2 failed/1 skipped；Backend 3 failed + 依赖阻断 | 当前基线 |
| [Frontend 模块化与 Agent 验证 2026-09-22](frontend-modularity-agent-validation-2026-09-22.md) | 节点实例自定义通过；模块化/Prompt 编排部分通过 | 当前专项基线 |
| [Workflow 组件化审计 2026-09-23](workflow-componentization-audit-2026-09-23.md) | 模块骨架完成，执行/Agent 主链存在 P0 断点 | 当前最新专项基线 |
| [模块化第二轮纵向验收 2026-09-28](module-round2-validation-2026-09-28.md) | Module E2E、module_usage、Agent Parser/gate 通过 | 当前最新纵向证据 |
| [Platform Hardening 审计 2026-10-10](platform-audit-2026-10-10.md) | Phase M3 完成，转入共享契约/迁移/配置/发布治理 | 当前最新状态基线 |
| [项目验证 2026-10-15](project-validation-2026-10-15.md) | Frontend 387、Backend专项153、共享Catalog/Trace119；真实主链已通 | 当前最新状态基线 |
| [项目全量验证 2026-10-16](project-validation-2026-10-16.md) | 本地 H0-H4/H6 收口；Backend 2177、Frontend 414、Chromium 143 全绿 | 当前最新本地验收基线 |
| [真实链路 UAT 2026-10-12](real-chain-uat-2026-10-12.md) | MiMo/Qwen Image/Wan3 最小链路成功，含产物哈希 | 历史真实证据；执行 SHA/费用未捕获，不能替代当前提交复证 |
| [滑雪教学真实工作流 UAT 2026-10-16](ski-lesson-uat-2026-10-16.md) | 2 图→2×3s 视频→6.06s 合成技术链通过；内容固定器硬约束未通过 | 技术通过 / 内容外部阻断 |
| [Performance/Recovery 2026-10-16](performance-recovery-validation-2026-10-16.md) | Performance 19 passed；Recovery 55 passed | 当前本地基线 |
| [v1.0.0-rc.1 发布证据 2026-10-19](rc-release-2026-10-19.md) | `a2b6079` 三平台、Integration、Browser E2E、Security 全绿；tag/artifacts 已归档 | 当前 RC 发布基线 |

## 证据要求

报告用于证明某个 commit 在特定环境下的结果，至少应包含：

- 测试日期和时区；
- git commit SHA 与工作区状态；
- OS、Node、Python 和外部工具版本；
- 依赖锁文件或安装命令；
- 精确测试命令；
- 原始 passed/failed/skipped 输出；
- 外部 API 模型、地域和非敏感参数；
- 成本与产物校验。

当前两份报告的日期是 2026-09-17，晚于 2026-09-16 状态基线。发布前需由报告作者确认日期和环境来源。
