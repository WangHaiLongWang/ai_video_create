# 运维文档索引

| 文档 | 用途 |
|---|---|
| [INSTALL.md](INSTALL.md) | Node/Python/依赖安装、环境变量与启动 |
| [UPGRADE.md](UPGRADE.md) | 备份、升级、迁移与升级后验证 |
| [ROLLBACK.md](ROLLBACK.md) | 数据恢复、代码/依赖回退与风险 |
| [RELEASE-CHECKLIST.md](RELEASE-CHECKLIST.md) | RC 门禁、同 SHA 证据、tag 与归档 |
| [KNOWN-ISSUES.md](KNOWN-ISSUES.md) | 已知限制与外部 Provider 阻断 |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | 常见问题诊断 |
| [SECURITY.md](SECURITY.md) | 安全配置与漏洞报告 |

数据库维护命令：

```powershell
.\scripts\backup-db.ps1
.\scripts\restore-db.ps1 -BackupFile data\backups\<backup>.db
```

```bash
./scripts/backup-db.sh
./scripts/restore-db.sh data/backups/<backup>.db
```

备份脚本使用 SQLite 在线备份 API，生成 `.db.json`（包含大小与 SHA-256）；恢复前会自动创建 `pre-restore` 安全备份。
