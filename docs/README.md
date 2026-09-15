# ai_video_create 文档索引

## 当前基线

1. `PROJECT-STATUS.md`：项目完成度、测试证据、风险和下一批工单。开始开发前先阅读。
2. `plans/2026-09-15-company-delivery-plan.md`：唯一 Active 交付计划，包含工单、Sprint、门禁和发布策略。
3. `prd.md`：v1.0 产品范围与验收需求。
4. `dp.md`：目标架构和 Provider 边界。

## Provider 集成

- `integrations/mimo-v2.5-pro.md`：Xiaomi MiMo LLM 及通用 OpenAI-compatible 自定义配置。
- `integrations/qwen-image-3.0.md`：Qwen Image 3.0 官方协议、参数和当前验证状态。
- `integrations/wan3-video.md`：Wan3.0 视频、480P 默认值、异步任务及与 ComfyUI 的边界。

## 架构决策

- `adr/ADR-0001-provider-capability-boundaries.md`：按 text/image/video 能力拆分 Provider，并明确 Wan3 与 ComfyUI 的边界。

## 历史计划

`plans/README.md` 列出了历史方案。标记为 Superseded 的文档只用于追溯，不作为任务领取或完成度依据。

## 更新规则

- 每个 Sprint Demo 后更新 `PROJECT-STATUS.md` 的测试数字和里程碑。
- 需求变更先更新 PRD，再修改 Active 计划。
- 架构决策进入 `docs/adr/`；Provider 官方参数进入 `docs/integrations/`。
- “完成”必须具备代码、自动测试、主路径接入和验收证据。
