#!/usr/bin/env bash
# ============================================================
# SQLite Database Restore Script
# Restores a database from a backup file. Creates a safety
# backup of the current DB before overwriting.
#
# Usage:  ./scripts/restore-db.sh <backup_file>
# ============================================================

set -euo pipefail

# ---- Configuration ----
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="${AI_VIDEO_DB_PATH:-${PROJECT_ROOT}/data/ai_video_create.db}"

# ---- Helpers ----
info()  { printf "\033[32m[INFO]\033[0m  %s\n" "$*"; }
warn()  { printf "\033[33m[WARN]\033[0m  %s\n" "$*"; }
error() { printf "\033[31m[ERROR]\033[0m %s\n" "$*" >&2; exit 1; }

# ---- Arguments ----
if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Restore the SQLite database from a backup file."
    echo "A safety backup of the current database is created before restore."
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    error "Backup file not found: ${BACKUP_FILE}"
fi

# ---- Verify backup integrity ----
info "Verifying backup integrity..."

if command -v sqlite3 &>/dev/null; then
    INTEGRITY=$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" 2>&1)
    if [ "$INTEGRITY" != "ok" ]; then
        error "Backup integrity check failed: ${INTEGRITY}"
    fi
    info "Integrity check passed"
else
    # Basic validation
    FILE_SIZE=$(wc -c < "$BACKUP_FILE" | tr -d ' ')
    if [ "$FILE_SIZE" -lt 100 ]; then
        error "Backup file too small (${FILE_SIZE} bytes) — likely corrupt"
    fi
    warn "No sqlite3 CLI — skipping detailed integrity check"
fi

# ---- Safety backup of current DB ----
if [ -f "$DB_PATH" ]; then
    SAFETY_TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
    SAFETY_BACKUP="${DB_PATH}.pre-restore-${SAFETY_TIMESTAMP}"
    info "Creating safety backup: ${SAFETY_BACKUP}"
    cp "$DB_PATH" "$SAFETY_BACKUP"
    # Copy WAL/SHM if present
    [ -f "${DB_PATH}-wal" ] && cp "${DB_PATH}-wal" "${SAFETY_BACKUP}-wal"
    [ -f "${DB_PATH}-shm" ] && cp "${DB_PATH}-shm" "${SAFETY_BACKUP}-shm"
    info "Safety backup created"
else
    warn "No existing database found — will create fresh from backup"
fi

# ---- Restore ----
info "Restoring database from ${BACKUP_FILE}..."

# Ensure data directory exists
DB_DIR="$(dirname "$DB_PATH")"
mkdir -p "$DB_DIR"

# Copy backup to target location
cp "$BACKUP_FILE" "$DB_PATH"

# Copy WAL/SHM if present in backup
[ -f "${BACKUP_FILE}-wal" ] && cp "${BACKUP_FILE}-wal" "${DB_PATH}-wal"
[ -f "${BACKUP_FILE}-shm" ] && cp "${BACKUP_FILE}-shm" "${DB_PATH}-shm"

# Remove stale journal file if it exists (WAL backup might conflict)
rm -f "${DB_PATH}-journal"

# ---- Verify restored DB ----
info "Verifying restored database..."

if command -v sqlite3 &>/dev/null; then
    INTEGRITY=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1)
    if [ "$INTEGRITY" = "ok" ]; then
        info "Restored database integrity check passed"
    else
        error "Restored database is corrupt: ${INTEGRITY}"
    fi

    # Quick sanity check: verify tables exist
    TABLE_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>&1)
    info "Database contains ${TABLE_COUNT} table(s)"
else
    FILE_SIZE=$(wc -c < "$DB_PATH" | tr -d ' ')
    info "Restored file size: ${FILE_SIZE} bytes (no sqlite3 for detailed check)"
fi

# ---- Summary ----
DB_SIZE=$(wc -c < "$DB_PATH" | tr -d ' ')
info "Restore complete. Database: ${DB_PATH} (${DB_SIZE} bytes)"
