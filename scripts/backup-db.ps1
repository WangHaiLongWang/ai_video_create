param([string]$BackupDir, [int]$KeepCount = 10, [string]$Database)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { $Python = "python" }
if (-not $Database) { $Database = if ($env:AI_VIDEO_DB_PATH) { $env:AI_VIDEO_DB_PATH } else { Join-Path $ProjectRoot "data\ai_video_create.db" } }
if (-not $BackupDir) { $BackupDir = Join-Path $ProjectRoot "data\backups" }
& $Python (Join-Path $PSScriptRoot "db-maintenance.py") backup --database $Database --backup-dir $BackupDir --keep $KeepCount
exit $LASTEXITCODE
