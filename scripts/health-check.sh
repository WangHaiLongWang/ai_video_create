#!/usr/bin/env bash
# ============================================================
# System Health Check Script
# Checks backend server, database, FFmpeg, and disk space.
# Outputs a JSON status report.
#
# Usage:  ./scripts/health-check.sh [--json] [--quiet]
# ============================================================

set -euo pipefail

# ---- Configuration ----
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="${AI_VIDEO_DB_PATH:-${PROJECT_ROOT}/data/ai_video_create.db}"
HOST="${AI_VIDEO_HOST:-127.0.0.1}"
PORT="${AI_VIDEO_PORT:-8000}"
ASSET_DIR="${AI_VIDEO_ASSET_DIR:-${PROJECT_ROOT}/data/assets}"
FFMPEG_PATH="${AI_VIDEO_FFMPEG_PATH:-ffmpeg}"

JSON_MODE=false
QUIET=false

for arg in "$@"; do
    case "$arg" in
        --json)  JSON_MODE=true ;;
        --quiet) QUIET=true ;;
    esac
done

# ---- Helpers ----
info()  { $QUIET || printf "\033[32m[INFO]\033[0m  %s\n" "$*"; }
warn()  { $QUIET || printf "\033[33m[WARN]\033[0m  %s\n" "$*"; }

# Accumulate results
declare -a CHECKS=()

add_check() {
    local name="$1" status="$2" message="$3"
    CHECKS+=("{\"name\":\"${name}\",\"status\":\"${status}\",\"message\":\"${message}\"}")
}

# ---- 1. Backend Server ----
info "Checking backend server at ${HOST}:${PORT}..."

if command -v curl &>/dev/null; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://${HOST}:${PORT}/docs" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "307" ] || [ "$HTTP_CODE" = "302" ]; then
        add_check "backend_server" "healthy" "Server responding on ${HOST}:${PORT} (HTTP ${HTTP_CODE})"
        info "Backend server is running (HTTP ${HTTP_CODE})"
    else
        add_check "backend_server" "unreachable" "Server not responding (HTTP ${HTTP_CODE})"
        warn "Backend server not responding (HTTP ${HTTP_CODE})"
    fi
elif command -v wget &>/dev/null; then
    if wget -q -O /dev/null --timeout=5 "http://${HOST}:${PORT}/docs" 2>/dev/null; then
        add_check "backend_server" "healthy" "Server responding on ${HOST}:${PORT}"
        info "Backend server is running"
    else
        add_check "backend_server" "unreachable" "Server not responding"
        warn "Backend server not responding"
    fi
else
    # Fall back to TCP check
    if (echo > /dev/tcp/"${HOST}"/"${PORT}") 2>/dev/null; then
        add_check "backend_server" "healthy" "Port ${PORT} is open (no HTTP check available)"
        info "Port ${PORT} is open"
    else
        add_check "backend_server" "unreachable" "Port ${PORT} is closed"
        warn "Port ${PORT} is closed"
    fi
fi

# ---- 2. Database Connectivity ----
info "Checking database at ${DB_PATH}..."

if [ ! -f "$DB_PATH" ]; then
    add_check "database" "missing" "Database file not found at ${DB_PATH}"
    warn "Database file not found"
elif command -v sqlite3 &>/dev/null; then
    # Integrity check
    INTEGRITY=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1)
    TABLE_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>&1)
    DB_SIZE=$(wc -c < "$DB_PATH" | tr -d ' ')

    if [ "$INTEGRITY" = "ok" ]; then
        add_check "database" "healthy" "Integrity OK, ${TABLE_COUNT} tables, ${DB_SIZE} bytes"
        info "Database: integrity OK, ${TABLE_COUNT} tables (${DB_SIZE} bytes)"
    else
        add_check "database" "corrupt" "Integrity check failed: ${INTEGRITY}"
        warn "Database integrity check failed: ${INTEGRITY}"
    fi

    # Check WAL mode
    JOURNAL=$(sqlite3 "$DB_PATH" "PRAGMA journal_mode;" 2>&1)
    if [ "$JOURNAL" = "wal" ]; then
        add_check "database_wal" "healthy" "WAL mode enabled"
        info "WAL mode: enabled"
    else
        add_check "database_wal" "warning" "Journal mode: ${JOURNAL} (expected wal)"
        warn "Journal mode is ${JOURNAL}, expected wal"
    fi
else
    DB_SIZE=$(wc -c < "$DB_PATH" | tr -d ' ')
    HEADER=$(xxd -l 16 -p "$DB_PATH" 2>/dev/null || echo "")
    if [ "$DB_SIZE" -gt 100 ] && [[ "$HEADER" == 53514c69746520666f726d6174203300* ]]; then
        add_check "database" "healthy" "File exists (${DB_SIZE} bytes), valid header (no sqlite3 CLI for full check)"
        info "Database file exists and has valid SQLite header (${DB_SIZE} bytes)"
    else
        add_check "database" "warning" "File exists (${DB_SIZE} bytes) but cannot verify integrity (no sqlite3 CLI)"
        warn "Cannot fully verify database (no sqlite3 CLI)"
    fi
fi

# ---- 3. FFmpeg Availability ----
info "Checking FFmpeg..."

if command -v "$FFMPEG_PATH" &>/dev/null; then
    FFMPEG_VERSION=$("$FFMPEG_PATH" -version 2>/dev/null | head -1 | awk '{print $3}')
    add_check "ffmpeg" "healthy" "Found: ${FFMPEG_VERSION}"
    info "FFmpeg: version ${FFMPEG_VERSION}"
else
    add_check "ffmpeg" "missing" "FFmpeg not found at '${FFMPEG_PATH}'"
    warn "FFmpeg not found at '${FFMPEG_PATH}'"
fi

# ---- 4. Disk Space ----
info "Checking disk space..."

DISK_OUTPUT=$(df -h "$PROJECT_ROOT" 2>/dev/null | tail -1)
if [ -n "$DISK_OUTPUT" ]; then
    # Parse df output (columns: Filesystem Size Used Avail Use% Mounted)
    AVAIL=$(echo "$DISK_OUTPUT" | awk '{print $4}')
    USE_PCT=$(echo "$DISK_OUTPUT" | awk '{print $5}' | tr -d '%')

    if [ -n "$USE_PCT" ] && [ "$USE_PCT" -ge 90 ]; then
        add_check "disk_space" "critical" "Only ${AVAIL} free (${USE_PCT}% used)"
        warn "Disk space critical: ${AVAIL} free (${USE_PCT}% used)"
    elif [ -n "$USE_PCT" ] && [ "$USE_PCT" -ge 75 ]; then
        add_check "disk_space" "warning" "${AVAIL} free (${USE_PCT}% used)"
        warn "Disk space getting low: ${AVAIL} free (${USE_PCT}% used)"
    else
        add_check "disk_space" "healthy" "${AVAIL} free (${USE_PCT}% used)"
        info "Disk space: ${AVAIL} free (${USE_PCT}% used)"
    fi
else
    add_check "disk_space" "unknown" "Cannot determine disk space"
    warn "Cannot determine disk space"
fi

# ---- 5. Asset Directory ----
info "Checking asset directory..."

if [ -d "$ASSET_DIR" ]; then
    ASSET_COUNT=$(find "$ASSET_DIR" -type f 2>/dev/null | wc -l | tr -d ' ')
    ASSET_SIZE=$(du -sh "$ASSET_DIR" 2>/dev/null | awk '{print $1}')
    add_check "asset_dir" "healthy" "${ASSET_COUNT} files, ${ASSET_SIZE} total"
    info "Asset directory: ${ASSET_COUNT} files (${ASSET_SIZE})"
else
    add_check "asset_dir" "missing" "Asset directory not found at ${ASSET_DIR}"
    warn "Asset directory not found: ${ASSET_DIR}"
fi

# ---- Output JSON Report ----
CHECKS_JSON=$(IFS=,; echo "${CHECKS[*]}")

# Determine overall status
OVERALL="healthy"
for check in "${CHECKS[@]}"; do
    if echo "$check" | grep -q '"status":"unreachable"\|"status":"corrupt"\|"status":"critical"\|"status":"missing"'; then
        OVERALL="degraded"
        break
    fi
    if echo "$check" | grep -q '"status":"warning"'; then
        OVERALL="warning"
    fi
done

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

JSON_REPORT=$(cat <<EOF
{
  "timestamp": "${TIMESTAMP}",
  "overall": "${OVERALL}",
  "project_root": "${PROJECT_ROOT}",
  "checks": [${CHECKS_JSON}]
}
EOF
)

if $JSON_MODE; then
    echo "$JSON_REPORT"
else
    echo ""
    echo "========================================"
    echo " Health Check Report"
    echo "========================================"
    echo ""
    echo "$JSON_REPORT" | python3 -m json.tool 2>/dev/null || echo "$JSON_REPORT"
    echo ""
    echo "========================================"
    echo " Overall: $(echo "$OVERALL" | tr '[:lower:]' '[:upper:]')"
    echo "========================================"
fi

# Exit with error code if degraded
if [ "$OVERALL" = "degraded" ]; then
    exit 1
fi
