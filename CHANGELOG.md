# Changelog

所有用户可见变更按版本记录；格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)。安装、升级、回滚与 RC 检查见 [`docs/operations/`](docs/operations/README.md)。

## [1.0.0-rc.1] - 2026-10-16

### Added

- 统一发布版本来源 [`VERSION`](VERSION)，并让前端 package、后端 API health/OpenAPI 使用同一版本。
- 可复现发布清单与 SHA-256 依赖/构建元数据校验。
- SQLite 备份、恢复与升级前安全备份脚本（PowerShell 与 POSIX shell）。
- RC 发布检查、安装/升级/回滚演练文档。
- Browser E2E 与 Linux/Windows/macOS CI、Agent v2 structured intent、Scene JSON roundtrip、模块化节点与 Doubao Provider 契约。

### Verification

- 本地发布清单：`python scripts/verify-release-metadata.py`
- 生成校验文件：`python scripts/release-manifest.py`
- 完整门禁：`npm run preflight`、前端 Vitest/typecheck/build、后端 pytest。

### Known issues

- 同 SHA 远端三平台 CI 证据需在 GitHub Actions 运行后归档。
- Doubao Seedream/Seedance 真实 UAT 仍依赖火山方舟账号激活；Mock/契约测试不代表上游可用。

### Fixed

- 端口 ID/方向/基数校验、React Flow 连线和多节点拖拽、CI health probe、Agent v1 兼容层。
- Provider 错误不再生成假成功资产；密钥使用 AES-GCM 加密且 API 不回显。

## [1.0.0-beta.3] - 2026-09-18

### Added

- Scene Draft SQLite 持久化、Scene Editor 锁定/解锁、TaskPreview 与 Provider 错误 UI。
- Canvas viewport/selection/copy-paste 的 undo/redo。

### Fixed

- React Flow edge reconnect、动态端口删除级联、viewport transform 后的坐标处理。

## [1.0.0-beta.2] - 2026-09-15

### Added

- WorkflowSpec v2 typed node manifest、Agent v1→v2 structured intent、模板持久化与四套内置模板。

### Fixed

- Template 与 Agent compiler 的 edge handle/port ID 一致性。

## [1.0.0-beta.1] - 2026-09-10

### Added

- React Flow canvas、FastAPI workflow CRUD/execution/provider、Mock provider 与基础 CI。
