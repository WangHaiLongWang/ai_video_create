#!/usr/bin/env bash
# ============================================================
# SQLite Database Backup Script
# Copies the database to a timestamped backup, verifies
# integrity, and optionally prunes old backups.
#
# Usage:  ./scripts/backup-db.sh [backup_dir]
#   backup_dir  — where to store backups (default: data/backups)
# ============================================================

set -euo pipefail

# ---- Configuration ----
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="${AI_VIDEO_DB_PATH:-${PROJECT_ROOT}/data/ai_video_create.db}"
BACKUP_DIR="${1:-${PROJECT_ROOT}/data/backups}"
KEEP_COUNT="${AI_VIDEO_BACKUP_KEEP:-10}"

TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
BACKUP_FILE="${BACKUP_DIR}/ai_video_create_${TIMESTAMP}.db"

# ---- Helpers ----
info()  { printf "\033[32m[INFO]\033[0m  %s\n" "$*"; }
warn()  { printf "\033[33m[WARN]\033[0m  %s\n" "$*"; }
error() { printf "\033[31m[ERROR]\033[0m %s\n" "$*" >&2; exit 1; }

# ---- Pre-flight ----
if [ ! -f "$DB_PATH" ]; then
    error "Database not found at ${DB_PATH}"
fi

if ! command -v sqlite3 &>/dev/null; then
    warn "sqlite3 CLI not found — will use file copy instead of .backup command"
fi

mkdir -p "$BACKUP_DIR"

# ---- Backup ----
info "Backing up ${DB_PATH} -> ${BACKUP_FILE}"

if command -v sqlite3 &>/dev/null; then
    # Use SQLite's .backup command (safe even with active WAL)
    sqlite3 "$DB_PATH" ".backup '${BACKUP_FILE}'"
else
    cp "$DB_PATH" "$BACKUP_FILE"
fi

# Copy WAL / SHM files if they exist (offline copy)
WAL_FILE="${DB_PATH}-wal"
SHM_FILE="${DB_PATH}-shm"
if [ -f "$WAL_FILE" ]; then
    cp "$WAL_FILE" "${BACKUP_FILE}-wal"
    info "Copied WAL file"
fi
if [ -f "$SHM_FILE" ]; then
    cp "$SHM_FILE" "${BACKUP_FILE}-shm"
    info "Copied SHM file"
fi

# ---- Verify ----
info "Verifying backup integrity..."

if command -v sqlite3 &>/dev/null; then
    INTEGRITY=$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" 2>&1)
    if [ "$INTEGRITY" = "ok" ]; then
        info "Integrity check passed"
    else
        rm -f "$BACKUP_FILE" "${BACKUP_FILE}-wal" "${BACKUP_FILE}-shm"
        error "Integrity check failed: ${INTEGRITY}"
    fi
else
    # Basic validation: file is non-zero and starts with SQLite header
    FILE_SIZE=$(wc -c < "$BACKUP_FILE" | tr -d ' ')
    HEADER=$(xxd -l 16 -p "$BACKUP_FILE" 2>/dev/null || echo "")
    if [ "$FILE_SIZE" -lt 100 ]; then
        rm -f "$BACKUP_FILE"
        error "Backup file too small (${FILE_SIZE} bytes) — likely corrupt"
    elif [ -n "$HEADER" ] && [[ "$HEADER" == 53514c69746520666f726d6174203300* ]]; then
        info "Header check passed (${FILE_SIZE} bytes)"
    else
        warn "Cannot fully verify (no sqlite3 CLI); file size: ${FILE_SIZE} bytes"
    fi
fi

# ---- Prune old backups ----
BACKUP_COUNT=$(find "$BACKUP_DIR" -maxdepth 1 -name "ai_video_create_*.db" -type f | wc -l | tr -d ' ')
if [ "$BACKUP_COUNT" -gt "$KEEP_COUNT" ]; then
    DELETE_COUNT=$((BACKUP_COUNT - KEEP_COUNT))
    info "Pruning ${DELETE_COUNT} old backup(s) (keeping last ${KEEP_COUNT})..."
    find "$BACKUP_DIR" -maxdepth 1 -name "ai_video_create_*.db" -type f | sort | head -n "$DELETE_COUNT" | while read -r old; do
        rm -f "$old" "${old}-wal" "${old}-shm"
        info "  Removed $(basename "$old")"
    done
fi

# ---- Summary ----
FINAL_COUNT=$(find "$BACKUP_DIR" -maxdepth 1 -name "ai_video_create_*.db" -type f | wc -l | tr -d ' ')
BACKUP_SIZE=$(wc -c < "$BACKUP_FILE" | tr -d ' ')
info "Done. Backup: ${BACKUP_FILE} (${BACKUP_SIZE} bytes)"
info "Total backups in ${BACKUP_DIR}: ${FINAL_COUNT}"
