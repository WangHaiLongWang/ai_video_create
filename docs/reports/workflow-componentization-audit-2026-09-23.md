# Workflow 组件化与 Agent 编排审计报告

> 日期：2026-09-23
> Commit：`27f8573`
> 方法：主 Agent + 3 个 subagent 独立审计（架构、Frontend、Workflow Agent）

## 1. 判定

当前属于“模块化骨架已建立、生产闭环未打通”。

| 维度 | 成熟度 | 判定 |
|---|---:|---|
| Module 契约/存储代码 | 75% | Schema、Repository、API、生命周期代码存在 |
| Frontend 组件化体验 | 60% | Palette/Designer/drop 已有，保存、远端解析、端口 binding 有断点 |
| Agent 模块编排 | 35% | discovery/parser 基础存在，compiler/repair/apply gate 未贯通 |
| 模块真实执行 | 25% | Resolver 存在，但 effective config 未可靠进入 Task/Handler |
| 综合组件化闭环 | **约 50%–55%** | 不可声明生产完成 |

## 2. 自动测试证据

```text
Backend module selection: 161 passed / 10 failed
Frontend module unit:     38 passed（另有 DOM nesting/act warning）
Agent core audit:         478 passed，但未覆盖关键 module compiler/repair 断点
```

10 个后端失败集中在 clone 后 Registry 结构污染，导致 Agent 无法列出模块或把模块目录注入 system prompt。

## 3. 已实现

- ModuleDefinition、NodeInstance module reference、config overrides。
- SQLite migration/repository 和模块 CRUD/clone/publish/archive API。
- ModulePalette、ModuleDesigner、ModuleCard，Canvas module drop。
- Module diff、dependency、安全、port binding、性能组件。
- ExecutionResolver 和 start 前调用。
- Agent module tools、WorkflowIntent moduleId、structured parser 基础。

## 4. P0 断点

1. Resolver 返回 effective config，但 Compiler 仍编译原 spec；Scheduler 恢复路径绕过 Resolver。
2. Registry/Repository wiring 不稳定；clone 内存回退污染 version map。
3. Frontend Designer API 与 Backend 路由/body 不一致，保存不可用。
4. Publish 未统一执行 schema/security/binding/provider gate。
5. Agent Compiler 丢 moduleId/version/overrides。
6. Agent repair wrapper 错用参数和 RepairResult；修复后 compiled graph 可能过期。
7. can_apply 未覆盖 compile + graph + module + resolver。
8. image-only fallback 产生 image → output.video 类型冲突。
9. PropertyPanel 仅识别静态 builtin；drop 未完整应用 module ports。
10. Module Designer 端口只读，没有 binding 编辑。
11. Workflow roundtrip 可能丢 fieldSchema/ports；required 转换丢失。
12. SemVer/capability/module_usage 和精确版本 config merge 存在错误。

## 5. 目标闭环

```text
Create Draft
→ Validate/Publish immutable version
→ Palette drag exact module version
→ Schema-driven config override
→ Module-aware port connection
→ Save/Reload exact reference
→ Materialize immutable resolved snapshot
→ Compile/Queue/Handler
→ Asset/Result
```

Agent 目标：

```text
Prompt
→ constraints
→ published module discovery
→ module-aware WorkflowIntent
→ compile
→ Intent/Graph/Module/Resolver validate
→ bounded repair + recompile
→ preview/diff/cost
→ confirm/apply/reload/run
```

## 6. 下一步

以 [`MODULAR-NODE-SEEDREAM-PLAN.md`](../plans/archive/MODULAR-NODE-SEEDREAM-PLAN.md) 的 Phase M0-R 为最高优先级。最终验收必须检查 Task.config 和 Handler input 中确实包含模块 defaults + overrides，不能只检查 UI 或数据库保存。
