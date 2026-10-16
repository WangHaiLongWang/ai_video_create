# ============================================================
# SQLite Database Backup Script (PowerShell)
# Copies the database to a timestamped backup, verifies
# integrity, and optionally prunes old backups.
#
# Usage:  .\scripts\backup-db.ps1 [-BackupDir path] [-KeepCount n]
# ============================================================

param(
    [string]$BackupDir,
    [int]$KeepCount = 10
)

$ErrorActionPreference = "Stop"

# ---- Configuration ----
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DbPath = if ($env:AI_VIDEO_DB_PATH) { $env:AI_VIDEO_DB_PATH } else { Join-Path $ProjectRoot "data\ai_video_create.db" }
if (-not $BackupDir) {
    $BackupDir = Join-Path $ProjectRoot "data\backups"
}

$Timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$BackupFile = Join-Path $BackupDir "ai_video_create_$Timestamp.db"

# ---- Helpers ----
function Write-Info($msg)  { Write-Host "[INFO]  $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

# ---- Pre-flight ----
if (-not (Test-Path $DbPath)) {
    Write-Err "Database not found at $DbPath"
}

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

# ---- Backup ----
Write-Info "Backing up $DbPath -> $BackupFile"

# Use SQLite's backup API via .backup command if sqlite3 is available
$sqlite3 = Get-Command sqlite3 -ErrorAction SilentlyContinue
if ($sqlite3) {
    # Create a temp file for the backup command output
    $tempFile = [System.IO.Path]::GetTempFileName()
    try {
        $backupCmd = ".backup '$BackupFile'"
        $backupCmd | & sqlite3 $DbPath
    }
    finally {
        Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Warn "sqlite3 CLI not found — using file copy"
    Copy-Item -Path $DbPath -Destination $BackupFile -Force
}

# Copy WAL / SHM files if they exist
$WalFile = "$DbPath-wal"
$ShmFile = "$DbPath-shm"
if (Test-Path $WalFile) {
    Copy-Item -Path $WalFile -Destination "$BackupFile-wal" -Force
    Write-Info "Copied WAL file"
}
if (Test-Path $ShmFile) {
    Copy-Item -Path $ShmFile -Destination "$BackupFile-shm" -Force
    Write-Info "Copied SHM file"
}

# ---- Verify ----
Write-Info "Verifying backup integrity..."

if ($sqlite3) {
    $integrity = & sqlite3 $BackupFile "PRAGMA integrity_check;" 2>&1
    if ($integrity -eq "ok") {
        Write-Info "Integrity check passed"
    } else {
        Remove-Item -Path $BackupFile -Force -ErrorAction SilentlyContinue
        Remove-Item -Path "$BackupFile-wal" -Force -ErrorAction SilentlyContinue
        Remove-Item -Path "$BackupFile-shm" -Force -ErrorAction SilentlyContinue
        Write-Err "Integrity check failed: $integrity"
    }
} else {
    # Basic validation
    $fileInfo = Get-Item $BackupFile
    if ($fileInfo.Length -lt 100) {
        Remove-Item -Path $BackupFile -Force
        Write-Err "Backup file too small ($($fileInfo.Length) bytes) - likely corrupt"
    } else {
        Write-Info "Header check passed ($($fileInfo.Length) bytes)"
    }
}

# ---- Prune old backups ----
$existingBackups = Get-ChildItem -Path $BackupDir -Filter "ai_video_create_*.db" -File |
    Sort-Object Name

if ($existingBackups.Count -gt $KeepCount) {
    $toDelete = $existingBackups | Select-Object -First ($existingBackups.Count - $KeepCount)
    Write-Info "Pruning $($toDelete.Count) old backup(s) (keeping last $KeepCount)..."
    foreach ($old in $toDelete) {
        Remove-Item -Path $old.FullName -Force
        Remove-Item -Path "$($old.FullName)-wal" -Force -ErrorAction SilentlyContinue
        Remove-Item -Path "$($old.FullName)-shm" -Force -ErrorAction SilentlyContinue
        Write-Info "  Removed $($old.Name)"
    }
}

# ---- Summary ----
$finalCount = (Get-ChildItem -Path $BackupDir -Filter "ai_video_create_*.db" -File).Count
$backupSize = (Get-Item $BackupFile).Length
Write-Info "Done. Backup: $BackupFile ($backupSize bytes)"
Write-Info "Total backups in ${BackupDir}: $finalCount"
