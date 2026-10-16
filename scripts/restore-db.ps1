param([Parameter(Mandatory = $true)][string]$BackupFile, [string]$Database)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { $Python = "python" }
if (-not $Database) { $Database = if ($env:AI_VIDEO_DB_PATH) { $env:AI_VIDEO_DB_PATH } else { Join-Path $ProjectRoot "data\ai_video_create.db" } }
& $Python (Join-Path $PSScriptRoot "db-maintenance.py") restore --database $Database --backup $BackupFile
exit $LASTEXITCODE
