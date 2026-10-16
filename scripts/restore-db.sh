#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -lt 1 ]; then echo "usage: $0 BACKUP_FILE [DATABASE]" >&2; exit 2; fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/backend/.venv/bin/python"; [ -x "$PYTHON" ] || PYTHON="${PYTHON_BIN:-python3}"
DATABASE="${2:-${AI_VIDEO_DB_PATH:-$ROOT/data/ai_video_create.db}}"
exec "$PYTHON" "$ROOT/scripts/db-maintenance.py" restore --database "$DATABASE" --backup "$1"
