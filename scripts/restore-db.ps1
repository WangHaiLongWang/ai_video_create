# ============================================================
# SQLite Database Restore Script (PowerShell)
# Restores a database from a backup file. Creates a safety
# backup of the current DB before overwriting.
#
# Usage:  .\scripts\restore-db.ps1 -BackupFile <path>
# ============================================================

param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile
)

$ErrorActionPreference = "Stop"

# ---- Configuration ----
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DbPath = if ($env:AI_VIDEO_DB_PATH) { $env:AI_VIDEO_DB_PATH } else { Join-Path $ProjectRoot "data\ai_video_create.db" }

# ---- Helpers ----
function Write-Info($msg)  { Write-Host "[INFO]  $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

# ---- Pre-flight ----
if (-not (Test-Path $BackupFile)) {
    Write-Err "Backup file not found: $BackupFile"
}

# ---- Verify backup integrity ----
Write-Info "Verifying backup integrity..."

$sqlite3 = Get-Command sqlite3 -ErrorAction SilentlyContinue
if ($sqlite3) {
    $integrity = & sqlite3 $BackupFile "PRAGMA integrity_check;" 2>&1
    if ($integrity -ne "ok") {
        Write-Err "Backup integrity check failed: $integrity"
    }
    Write-Info "Integrity check passed"
} else {
    $fileInfo = Get-Item $BackupFile
    if ($fileInfo.Length -lt 100) {
        Write-Err "Backup file too small ($($fileInfo.Length) bytes) - likely corrupt"
    }
    Write-Warn "No sqlite3 CLI - skipping detailed integrity check"
}

# ---- Safety backup of current DB ----
if (Test-Path $DbPath) {
    $safetyTimestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $safetyBackup = "$DbPath.pre-restore-$safetyTimestamp"
    Write-Info "Creating safety backup: $safetyBackup"
    Copy-Item -Path $DbPath -Destination $safetyBackup -Force
    $walPath = "$DbPath-wal"
    $shmPath = "$DbPath-shm"
    if (Test-Path $walPath) {
        Copy-Item -Path $walPath -Destination "$safetyBackup-wal" -Force
    }
    if (Test-Path $shmPath) {
        Copy-Item -Path $shmPath -Destination "$safetyBackup-shm" -Force
    }
    Write-Info "Safety backup created"
} else {
    Write-Warn "No existing database found - will create fresh from backup"
}

# ---- Restore ----
Write-Info "Restoring database from $BackupFile..."

$dbDir = Split-Path -Parent $DbPath
if (-not (Test-Path $dbDir)) {
    New-Item -ItemType Directory -Path $dbDir -Force | Out-Null
}

Copy-Item -Path $BackupFile -Destination $DbPath -Force

# Copy WAL/SHM if present in backup
$backupWal = "$BackupFile-wal"
$backupShm = "$BackupFile-shm"
if (Test-Path $backupWal) {
    Copy-Item -Path $backupWal -Destination "$DbPath-wal" -Force
}
if (Test-Path $backupShm) {
    Copy-Item -Path $backupShm -Destination "$DbPath-shm" -Force
}

# Remove stale journal file
$journalPath = "$DbPath-journal"
if (Test-Path $journalPath) {
    Remove-Item -Path $journalPath -Force
}

# ---- Verify restored DB ----
Write-Info "Verifying restored database..."

if ($sqlite3) {
    $integrity = & sqlite3 $DbPath "PRAGMA integrity_check;" 2>&1
    if ($integrity -eq "ok") {
        Write-Info "Restored database integrity check passed"
    } else {
        Write-Err "Restored database is corrupt: $integrity"
    }
    $tableCount = & sqlite3 $DbPath "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>&1
    Write-Info "Database contains $tableCount table(s)"
} else {
    $fileInfo = Get-Item $DbPath
    Write-Info "Restored file size: $($fileInfo.Length) bytes (no sqlite3 for detailed check)"
}

# ---- Summary ----
$dbSize = (Get-Item $DbPath).Length
Write-Info "Restore complete. Database: $DbPath ($dbSize bytes)"
