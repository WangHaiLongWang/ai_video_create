"""SQLite connection management with WAL mode and safe defaults."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_DB_PATH: Path | None = None
_CONNECTION: sqlite3.Connection | None = None

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _get_db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is None:
        # 默认放在项目根目录 data/ai_video_create.db
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        data_dir = project_root / "data"
        data_dir.mkdir(exist_ok=True)
        _DB_PATH = data_dir / "ai_video_create.db"
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
        conn.executescript(sql)
    conn.commit()
