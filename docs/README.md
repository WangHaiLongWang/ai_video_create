# ai_video_create 文档中心

## 从这里开始

| 文档 | 用途 | 更新时机 |
|---|---|---|
| [项目状态](PROJECT-STATUS.md) | 当前完成度、可重复测试、阻断项 | 每个 Sprint Demo 后 |
| [产品需求](product/PRD.md) | v1.0 范围、用户流程、验收要求 | 需求变化时 |
| [系统架构](architecture/SYSTEM-DESIGN.md) | 模块边界、数据流、Provider 架构 | 架构决策变化时 |
| [Active 交付计划](plans/active/DELIVERY-PLAN.md) | Sprint、工单、门禁和发布计划 | Planning/Review 后 |
| [Flow/Scene 专项计划](plans/active/FRONTEND-FLOW-SCENE-PLAN.md) | React Flow 连线、Scene 编辑与 Prompt 导出 | 专项 Review 后 |

阅读顺序：状态 → Active 计划 → 对应的产品/架构章节。

## 运维文档

| 文档 | 用途 |
|---|---|
| [安装指南](operations/INSTALL.md) | 从零开始的完整安装步骤、配置参考、平台说明 |
| [升级指南](operations/UPGRADE.md) | 版本升级流程、兼容性说明 |
| [回滚指南](operations/ROLLBACK.md) | 回滚到旧版本的步骤和数据考量 |
| [问题排查](operations/TROUBLESHOOTING.md) | 常见问题诊断和解决方案 |
| [安全指南](operations/SECURITY.md) | 安全特性、配置建议和漏洞报告 |

## AI Provider 集成

[查看集成索引](integrations/README.md)

| Provider | 文档 | 当前用途 |
|---|---|---|
| Xiaomi MiMo | [mimo-v2.5-pro.md](integrations/mimo-v2.5-pro.md) | 默认 LLM/分镜 |
| Qwen Image 3.0 | [qwen-image-3.0.md](integrations/qwen-image-3.0.md) | 默认文生图 |
| Wan3.0 Video | [wan3-video.md](integrations/wan3-video.md) | 默认图生视频 |

## 架构决策

- [ADR-0001：按能力拆分 Provider](architecture/adr/ADR-0001-provider-capability-boundaries.md)

重要架构决策进入 `architecture/adr/`，不埋在计划或状态报告中。

## 验收与测试报告

[查看报告索引](reports/README.md)

- [Wan3 真实 UAT](reports/wan3-uat.md)
- [FFmpeg 集成报告](reports/ffmpeg-integration.md)

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
├── operations/                       运维文档（安装、升级、回滚、排查、安全）
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
