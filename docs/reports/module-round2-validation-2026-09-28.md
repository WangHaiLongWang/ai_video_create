# Workflow 模块化第二轮纵向验收报告

> 日期：2026-09-28
> 基线：`70daa1d` + 第二轮工作区变更
> 范围：模块浏览器链路、module_usage、structured Agent Parser

## 1. 结论

第二轮纵向验收通过核心目标，模块化从“代码骨架”推进到“前端模块实例链路和后端引用追踪可验证”。本轮没有调用任何真实收费 Provider。

## 2. 验证结果

| 验证项 | 结果 |
|---|---:|
| Seedream modules Playwright | 3 passed |
| App + modules Chromium | 14 passed |
| Backend module_usage/registry/parser/resolver | 173 passed |
| Agent structured parser/module gate | 93 passed |
| Frontend typecheck | passed |
| Frontend production build | passed |

## 3. 通过链路

### Frontend

```text
published Seedream module
→ Module Palette
→ HTML5 drag/drop to Canvas
→ exact moduleId/version/ports/defaultConfig
→ PropertyPanel config override
→ localStorage reload
→ module reference and override preserved
```

Module Designer 的 create/save/publish 请求契约使用 route mock 验证，包括 version 与 expectedVersion。

### Backend module usage

- create：记录 module usage；
- update：删除旧引用并重建；
- remove reference：删除 stale usage；
- duplicate/import：使用新 workflow ID；
- delete：清理 usage；
- capability：按 providerPolicy.capability 过滤。

### Agent

- 图片专用请求移除非法 image→output.video；
- 两场景 × 两变体 × 5 秒配置正确写入节点；
- Seedream moduleId/version/overrides 经 Parser 和 Compiler 保真；
- unknown module 和 draft module 阻止 apply。

## 4. 本轮发现并修复

1. Canvas drop 坐标重复减去 wrapper bounds，导致节点落点偏移。
2. ModulePalette 独立 Grid child 产生隐式行，压缩/覆盖 Canvas；现合并到 library sidebar。
3. Workflow 保存未同步 module_usage。
4. ModuleRepository capability filter 错把 capability 当 base_kind。

## 5. 测试环境问题

- 默认 shell 曾解析到 Node 18，Playwright 要求 Node 20+；使用 Node 22.21.1 后 modules E2E 3/3 通过。
- Windows 并行运行 Vitest/Vite/Chromium时出现 `EMFILE`。串行 `--threads false` 又暴露 Testing Library cleanup 污染，说明测试隔离配置需要专项修复。
- 当前可采信的前端全量单元基线仍为第一轮的 342 passed；第二轮生产改动已由定向 unit、typecheck、build 和浏览器用例覆盖。

## 6. 下一步

按 [`MODULAR-NODE-SEEDREAM-PLAN.md`](../plans/active/MODULAR-NODE-SEEDREAM-PLAN.md) Phase M3 执行：真实 Mock Backend Playwright、端口 Binding Designer、module-aware graph validator、Modify E2E、测试隔离、CI 同 SHA 证据和真实 Seedream UAT。
