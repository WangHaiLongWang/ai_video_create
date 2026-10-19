# RC 发布检查清单

本清单用于 `v1.0.0-rc.1` 及后续版本。只有同一 Git SHA 的 required checks 全绿，才允许创建 tag；外部 Provider 阻断不能被本地 Mock 结果替代。

## 1. 版本与工作区

- [x] `git status --short` 只包含预期发布文件，`.env*`（示例除外）未被跟踪。
- [x] `python scripts/verify-release-metadata.py` 通过。
- [x] `VERSION`、根/前端 `package.json`、`backend/pyproject.toml`、`/api/health` 版本一致。
- [x] `git diff --check` 通过；验证提交 `a2b6079` 已记录。

## 2. 依赖与构建

- [x] Node 22.x / npm 10+，Python 3.12，且 `backend/constraints.txt` 已用于锁定安装。
- [x] `npm ci --prefix frontend`、`npm --prefix frontend run typecheck`、`npm --prefix frontend run build` 通过。
- [x] `python -m pytest backend/tests -m 'not external'` 通过；外部测试单独记录跳过原因。
- [x] `python scripts/release-manifest.py --output dist/release-manifest.json` 已生成并保存 `.sha256`。

## 3. 数据与回滚演练

- [x] 执行 `scripts/backup-db.ps1` 或 `scripts/backup-db.sh`，并通过 SQLite integrity check。
- [x] 在临时数据库上启动新版本，确认 migration ledger/checksum 通过。
- [x] 使用 `scripts/restore-db.*` 恢复备份；健康检查和关键工作流读取通过。
- [x] 升级失败时保留 pre-restore 安全备份，按 [`ROLLBACK.md`](ROLLBACK.md) 回退代码与依赖。

## 4. CI 与外部验收

- [x] 同一 SHA `a2b6079` 的 Linux/Windows/macOS required checks、browser-e2e、security/build artifacts 全绿；Actions URL 已归档。
- [x] MiMo/Qwen/Wan3 最小真实链路报告包含模型、参数、耗时、资产哈希、成本与脱敏 job id。
- [x] Doubao 未激活，发布记录明确 `External Blocked`，未标记为真实 UAT 通过。

## 5. Tag 与归档

```text
git tag -a v1.0.0-rc.1 <verified-sha> -m "ai_video_create v1.0.0-rc.1"
git show --stat --oneline v1.0.0-rc.1
```

Tag 已指向验证 SHA `a2b6079`；`release-manifest.json`、`.sha256`、测试报告、CI URL 和回滚演练记录已归档。
