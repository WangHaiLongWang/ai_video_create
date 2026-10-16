# ai_video_create 文档中心

## 从这里开始

| 文档 | 用途 | 更新时机 |
|---|---|---|
| [项目状态](PROJECT-STATUS.md) | 当前完成度、可重复测试、阻断项 | 每个 Sprint Demo 后 |
| [产品需求](product/PRD.md) | v1.0 范围、用户流程、验收要求 | 需求变化时 |
| [系统架构](architecture/SYSTEM-DESIGN.md) | 模块边界、数据流、Provider 架构 | 架构决策变化时 |
| [Active 交付计划](plans/active/DELIVERY-PLAN.md) | Sprint、工单、门禁和发布计划 | Planning/Review 后 |
| [长远路线图](plans/active/ROADMAP.md) | v1.0 后 12-18 个月版本列车、工程支柱与待决策项 | 版本出口/决策拍板后 |
| [Flow/Scene 专项计划](plans/archive/FRONTEND-FLOW-SCENE-PLAN.md) | React Flow 连线、Scene 编辑与 Prompt 导出 | 已归档，当前结论见状态页 |
| [滑雪教学验收工作流](plans/active/SKI-LESSON-WORKFLOW-PLAN.md) | 2 张照片 → 2 段 3 秒视频 → 合成 | 作为真实端到端目标 |
| [React Flow / Agent 计划](plans/archive/REACT-FLOW-AGENT-PLAN.md) | 自定义字段、连线恢复、Prompt 生成完整流程 | 已归档（功能完成） |
| [RC 收敛计划](plans/archive/RC-CLOSURE-PLAN.md) | 依赖、E2E、CI 和 v1.0.0-rc.1 门禁 | 已归档并被 Platform Hardening 取代 |
| [模块化节点与 Seedream](plans/archive/MODULAR-NODE-SEEDREAM-PLAN.md) | 可复用模块、Schema 属性组件和 Seedream 薄切片 | 已归档（Phase M0-M3 完成） |
| [Platform Hardening](plans/active/PLATFORM-HARDENING-PLAN.md) | 共享契约、迁移、Provider 持久化、CI/UAT 和 RC 发布 | 当前唯一推进主线 |

阅读顺序：状态 → Active 计划 → 对应的产品/架构章节。

## 运维文档

| 文档 | 用途 |
|---|---|
| [安装指南](operations/INSTALL.md) | 从零开始的完整安装步骤、配置参考、平台说明 |
| [升级指南](operations/UPGRADE.md) | 版本升级流程、兼容性说明 |
| [回滚指南](operations/ROLLBACK.md) | 回滚到旧版本的步骤和数据考量 |
| [已知问题](operations/KNOWN-ISSUES.md) | 当前版本的已知问题和平台限制 |
| [问题排查](operations/TROUBLESHOOTING.md) | 常见问题诊断和解决方案 |
| [安全指南](operations/SECURITY.md) | 安全特性、配置建议和漏洞报告 |
| [运维文档索引](operations/README.md) | 发布检查、数据库备份恢复与运维入口 |

## AI Provider 集成

[查看集成索引](integrations/README.md)

| Provider | 文档 | 当前用途 |
|---|---|---|
| Xiaomi MiMo | [mimo-v2.5-pro.md](integrations/mimo-v2.5-pro.md) | 默认 LLM/分镜 |
| Qwen Image 3.0 | [qwen-image-3.0.md](integrations/qwen-image-3.0.md) | 默认文生图 |
| Wan3.0 Video | [wan3-video.md](integrations/wan3-video.md) | 默认图生视频 |
| Doubao Seedream/Seedance | [doubao-seedance-2.5.md](integrations/doubao-seedance-2.5.md) | 可选图片/视频 Provider；当前模型未激活 |

## 架构决策

- [ADR-0001：按能力拆分 Provider](architecture/adr/ADR-0001-provider-capability-boundaries.md)

重要架构决策进入 `architecture/adr/`，不埋在计划或状态报告中。

## 验收与测试报告

[查看报告索引](reports/README.md)

- [Wan3 真实 UAT](reports/wan3-uat.md)
- [FFmpeg 集成报告](reports/ffmpeg-integration.md)
- [项目门禁审计 2026-09-21](reports/project-audit-2026-09-21.md)
- [Frontend 模块化与 Agent 验证 2026-09-22](reports/frontend-modularity-agent-validation-2026-09-22.md)
- [Workflow 组件化审计 2026-09-23](reports/workflow-componentization-audit-2026-09-23.md)
- [模块化第二轮纵向验收 2026-09-28](reports/module-round2-validation-2026-09-28.md)
- [Platform Hardening 审计 2026-10-10](reports/platform-audit-2026-10-10.md)
- [项目验证 2026-10-15](reports/project-validation-2026-10-15.md)

报告是特定环境下的证据，不自动代表当前分支门禁通过。报告必须包含日期、commit、环境、命令和原始结果。

## 研发计划

- `plans/active/`：唯一当前计划。
- `plans/archive/`：历史方案，仅供追溯。
- [计划索引](plans/README.md)

## 目录规范

```text
docs/
├── README.md                         文档入口
├── PROJECT-STATUS.md                 当前事实基线
├── product/                          产品需求
├── architecture/                     系统设计与 ADR
├── integrations/                     Provider 官方协议与配置
├── reports/                          UAT/集成/性能证据
├── operations/                       运维文档（安装、升级、回滚、已知问题、排查、安全）
└── plans/
    ├── active/                       当前唯一交付计划
    └── archive/                      已废弃历史计划
```

## 文档治理

- PRD 不记录实现百分比。
- 架构文档不复制 PRD，不记录短期任务状态。
- 当前实现只写 `PROJECT-STATUS.md`。
- 任务排期只写 Active 计划。
- Provider 参数只写 `integrations/`。
- 测试结果只写 `reports/`，并同步状态摘要。
- Superseded 文档不得作为任务领取或完成度依据。
