#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/backend/.venv/bin/python"; [ -x "$PYTHON" ] || PYTHON="${PYTHON_BIN:-python3}"
DATABASE="${AI_VIDEO_DB_PATH:-$ROOT/data/ai_video_create.db}"
BACKUP_DIR="${1:-$ROOT/data/backups}"; KEEP_COUNT="${2:-10}"
exec "$PYTHON" "$ROOT/scripts/db-maintenance.py" backup --database "$DATABASE" --backup-dir "$BACKUP_DIR" --keep "$KEEP_COUNT"
