"""SQLite connection management with WAL mode and safe defaults."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_DB_PATH: Path | None = None
_CONNECTION: sqlite3.Connection | None = None

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _get_db_path() -> Path:
    """Resolve the SQLite file path.

    Honors ``Settings.DB_PATH`` / ``AI_VIDEO_DB_PATH`` so test and E2E runs can
    point at an isolated database.  Relative values are resolved against the
    project root; when unset the historical ``data/ai_video_create.db`` location
    is used unchanged.
    """
    global _DB_PATH
    if _DB_PATH is None:
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        configured = os.environ.get("AI_VIDEO_DB_PATH", "").strip()
        if not configured:
            try:
                from backend.app.config import get_settings

                configured = (get_settings().DB_PATH or "").strip()
            except Exception:  # pragma: no cover - settings optional at import
                configured = ""
        # Keep the historical default when settings still carry it.
        if not configured or configured == "data/ai_video_create.db":
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            _DB_PATH = data_dir / "ai_video_create.db"
        else:
            path = Path(configured)
            if not path.is_absolute():
                path = project_root / path
            path.parent.mkdir(parents=True, exist_ok=True)
            _DB_PATH = path
    return _DB_PATH


def get_connection() -> sqlite3.Connection:
    """获取或创建 SQLite 连接（进程内单例）。"""
    global _CONNECTION
    if _CONNECTION is None:
        db_path = _get_db_path()
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        _CONNECTION = conn
    return _CONNECTION


def close_connection() -> None:
    global _CONNECTION
    if _CONNECTION is not None:
        _CONNECTION.close()
        _CONNECTION = None


def init_db() -> None:
    """执行迁移脚本初始化数据库（幂等）。"""
    conn = get_connection()
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for mf in migration_files:
        sql = mf.read_text(encoding="utf-8")
        # 按分号分割语句并逐个执行
        # 这样可以单独处理 ALTER TABLE 的 duplicate column 错误
        statements = []
        current = []
        for line in sql.split('\n'):
            stripped = line.strip()
            # 跳过空行和纯注释行
            if not stripped or stripped.startswith('--'):
                if current:  # 如果当前有积累的语句，保留注释
                    current.append(line)
                continue
            current.append(line)
            if stripped.endswith(';'):
                statements.append('\n'.join(current))
                current = []
        if current:
            statements.append('\n'.join(current))

        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    continue  # 列已存在，跳过
                raise
    conn.commit()
