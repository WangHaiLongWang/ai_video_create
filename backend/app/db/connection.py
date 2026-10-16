"""SQLite connection management with WAL mode and safe defaults."""

from __future__ import annotations

import os
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH: Path | None = None
_CONNECTION: sqlite3.Connection | None = None

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class MigrationError(RuntimeError):
    """Raised when a database migration cannot be applied safely."""


class MigrationChecksumError(MigrationError):
    """Raised when an already-applied migration file was modified."""


def _migration_statements(sql: str) -> list[str]:
    """Split repository migration SQL into executable statements."""
    statements: list[str] = []
    current: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current).strip())
            current = []
    if current:
        statements.append("\n".join(current).strip())
    return [statement for statement in statements if statement]


def _ensure_migration_ledger(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )"""
    )
    conn.commit()


def apply_migrations(
    conn: sqlite3.Connection,
    migrations_dir: Path | None = None,
) -> list[str]:
    """Apply pending migrations transactionally and verify checksums.

    Returns the versions applied during this call. Existing legacy databases
    are supported: idempotent DDL and duplicate-column ALTER statements are
    replayed once, then recorded in the ledger.
    """
    directory = migrations_dir or MIGRATIONS_DIR
    _ensure_migration_ledger(conn)
    applied_now: list[str] = []

    for migration_file in sorted(directory.glob("*.sql")):
        version = migration_file.name.split("_", 1)[0]
        sql = migration_file.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        existing = conn.execute(
            "SELECT filename, checksum FROM schema_migrations WHERE version = ?",
            (version,),
        ).fetchone()
        if existing is not None:
            if existing["checksum"] != checksum:
                raise MigrationChecksumError(
                    f"Migration {version} checksum mismatch: "
                    f"recorded {existing['filename']}, current {migration_file.name}"
                )
            continue

        savepoint = f"migration_{version.replace('-', '_')}"
        conn.execute(f"SAVEPOINT {savepoint}")
        try:
            for statement in _migration_statements(sql):
                try:
                    conn.execute(statement)
                except sqlite3.OperationalError as exc:
                    # One-time adoption path for databases created by the old
                    # replay-on-start runner. After ledgering, this is no
                    # longer used for the migration.
                    if "duplicate column name" in str(exc).lower():
                        continue
                    raise
            conn.execute(
                "INSERT INTO schema_migrations "
                "(version, filename, checksum, applied_at) VALUES (?, ?, ?, ?)",
                (
                    version,
                    migration_file.name,
                    checksum,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            applied_now.append(version)
        except Exception as exc:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise MigrationError(
                f"Failed to apply migration {migration_file.name}: {exc}"
            ) from exc

    conn.commit()
    return applied_now


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
    """Apply versioned migrations and initialize the database."""
    conn = get_connection()
    apply_migrations(conn)
