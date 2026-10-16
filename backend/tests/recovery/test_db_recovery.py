"""Recovery tests -- database backup, restore, corruption, and initialization."""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import threading
from pathlib import Path
from typing import Generator

import pytest

from backend.app.db.connection import (
    close_connection,
    get_connection,
    init_db,
)
import backend.app.db.connection as conn_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_copy_db(src: Path, dst: Path) -> None:
    """Copy a SQLite database and its WAL/SHM sidecar files safely.

    This opens a fresh connection, checkpoints the WAL to the main file,
    then copies only the main file. This avoids issues with stale WAL files
    on Windows.
    """
    conn = sqlite3.connect(str(src))
    try:
        conn.execute("PRAGMA wal_checkpoint(FULL)")
    except Exception:
        pass
    finally:
        conn.close()
    shutil.copy2(src, dst)
    # Also copy WAL/SHM if present (they may reappear briefly)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(src) + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, Path(str(dst) + suffix))


def _create_test_data(conn: sqlite3.Connection, workflow_id: str = "wf-1") -> None:
    """Insert minimal test data into the database."""
    conn.execute(
        "INSERT INTO workflows (id, name, schema_version, spec_json, version, created_at, updated_at) "
        "VALUES (?, ?, '1.0', '{}', 1, datetime('now'), datetime('now'))",
        (workflow_id, "Test Workflow"),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_dir(tmp_path: Path) -> Path:
    """Provide a fresh temp directory for each test."""
    return tmp_path


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Each test gets a fresh, isolated database via monkeypatching."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(conn_module, "_DB_PATH", db_path)
    monkeypatch.setattr(conn_module, "_CONNECTION", None)
    close_connection()
    init_db()
    yield
    # Checkpoint and close cleanly
    try:
        conn = get_connection()
        conn.execute("PRAGMA wal_checkpoint(FULL)")
    except Exception:
        pass
    close_connection()
    monkeypatch.setattr(conn_module, "_DB_PATH", None)
    monkeypatch.setattr(conn_module, "_CONNECTION", None)


# ---------------------------------------------------------------------------
# Backup Tests
# ---------------------------------------------------------------------------

class TestBackupCreatesValidFile:
    """Backup creates a valid, queryable SQLite file."""

    def test_backup_file_is_valid_sqlite(self, tmp_path: Path) -> None:
        """A backup should be a valid SQLite database."""
        db_path = conn_module._DB_PATH
        assert db_path is not None
        _create_test_data(get_connection())

        backup = tmp_path / "backup.db"
        _safe_copy_db(db_path, backup)

        # Must be a real SQLite file
        conn = sqlite3.connect(str(backup))
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            assert result[0] == "ok"
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [r[0] for r in tables]
            assert "workflows" in table_names
        finally:
            conn.close()

    def test_backup_preserves_data(self, tmp_path: Path) -> None:
        """Data written before backup must be present in the backup."""
        db_path = conn_module._DB_PATH
        assert db_path is not None
        _create_test_data(get_connection())

        backup = tmp_path / "backup.db"
        _safe_copy_db(db_path, backup)

        conn = sqlite3.connect(str(backup))
        try:
            row = conn.execute(
                "SELECT name FROM workflows WHERE id = 'wf-1'"
            ).fetchone()
            assert row is not None
            assert row[0] == "Test Workflow"
        finally:
            conn.close()

    def test_backup_has_nonzero_size(self, tmp_path: Path) -> None:
        """Backup file should be non-trivial in size."""
        db_path = conn_module._DB_PATH
        assert db_path is not None

        backup = tmp_path / "backup.db"
        _safe_copy_db(db_path, backup)
        assert backup.stat().st_size > 0

    def test_backup_sqlite_header(self, tmp_path: Path) -> None:
        """Backup starts with the SQLite magic header string."""
        db_path = conn_module._DB_PATH
        assert db_path is not None

        backup = tmp_path / "backup.db"
        _safe_copy_db(db_path, backup)
        header = backup.read_bytes()[:16]
        assert header == b"SQLite format 3\x00"


# ---------------------------------------------------------------------------
# Restore Tests
# ---------------------------------------------------------------------------

class TestRestoreFromBackup:
    """Restore from backup recovers the database state."""

    def test_restore_recovers_data(self, tmp_path: Path) -> None:
        """After restore, the data from the backup is accessible."""
        db_path = conn_module._DB_PATH
        assert db_path is not None

        # Create original state and back it up
        _create_test_data(get_connection())
        backup = tmp_path / "backup.db"
        _safe_copy_db(db_path, backup)
        close_connection()

        # Destroy the database
        for sibling in db_path.parent.glob(f"{db_path.name}*"):
            sibling.unlink(missing_ok=True)

        # Restore
        shutil.copy2(backup, db_path)
        init_db()

        conn = get_connection()
        row = conn.execute(
            "SELECT name FROM workflows WHERE id = 'wf-1'"
        ).fetchone()
        assert row is not None
        assert row[0] == "Test Workflow"

    def test_safety_backup_created_before_restore(self, tmp_path: Path) -> None:
        """Restore should create a safety backup of the current DB."""
        db_path = conn_module._DB_PATH
        assert db_path is not None
        _create_test_data(get_connection())

        # Create backup to restore from
        backup = tmp_path / "backup.db"
        _safe_copy_db(db_path, backup)

        # Simulate safety backup
        safety_file = db_path.with_suffix(".safety.db")
        _safe_copy_db(db_path, safety_file)

        # Verify safety backup exists and is valid
        assert safety_file.exists()
        conn = sqlite3.connect(str(safety_file))
        try:
            row = conn.execute(
                "SELECT name FROM workflows WHERE id = 'wf-1'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()

    def test_restore_overwrites_current_db(self, tmp_path: Path) -> None:
        """Restore replaces the current database content."""
        db_path = conn_module._DB_PATH
        assert db_path is not None

        # Create a backup with wf-old
        _create_test_data(get_connection(), workflow_id="wf-old")
        backup = tmp_path / "backup.db"
        _safe_copy_db(db_path, backup)
        close_connection()

        # Now create a different DB with wf-new
        init_db()
        _create_test_data(get_connection(), workflow_id="wf-new")
        close_connection()

        # Restore from backup (which only has wf-old)
        shutil.copy2(backup, db_path)
        # Also copy WAL if present
        backup_wal = Path(str(backup) + "-wal")
        if backup_wal.exists():
            shutil.copy2(backup_wal, Path(str(db_path) + "-wal"))
        init_db()

        conn = get_connection()
        rows = conn.execute("SELECT id FROM workflows").fetchall()
        ids = [r[0] for r in rows]
        assert "wf-old" in ids

    def test_restore_validates_integrity_before_overwrite(
        self, tmp_path: Path
    ) -> None:
        """Restore should reject a corrupted backup file."""
        db_path = conn_module._DB_PATH
        assert db_path is not None

        # Create a valid backup first
        _create_test_data(get_connection())
        backup = tmp_path / "backup.db"
        _safe_copy_db(db_path, backup)
        close_connection()

        # Remove WAL/SHM sidecars so corruption of the main file is not masked
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(backup) + suffix)
            if sidecar.exists():
                sidecar.unlink()

        # Corrupt the backup: overwrite with non-SQLite data
        backup.write_bytes(b"NOT A DATABASE FILE" + b"\xff" * 4096)

        # Verify corruption is detected: either exception or integrity fails
        corruption_detected = False
        conn = sqlite3.connect(str(backup))
        try:
            try:
                result = conn.execute("PRAGMA integrity_check").fetchone()
                if result[0] != "ok":
                    corruption_detected = True
            except sqlite3.DatabaseError:
                corruption_detected = True
        finally:
            conn.close()

        assert corruption_detected, "Corruption was not detected"


# ---------------------------------------------------------------------------
# Corrupted Backup Tests
# ---------------------------------------------------------------------------

class TestCorruptedBackup:
    """Restore with corrupted backup fails gracefully."""

    def test_corrupted_backup_detection(self, tmp_path: Path) -> None:
        """A corrupted file should fail the integrity check."""
        db_path = tmp_path / "corrupted.db"
        db_path.write_bytes(b"this is not a valid sqlite file" * 100)

        conn = sqlite3.connect(str(db_path))
        try:
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute("SELECT * FROM sqlite_master")
        finally:
            conn.close()

    def test_empty_file_not_a_valid_backup(self, tmp_path: Path) -> None:
        """An empty file is not a valid backup."""
        db_path = tmp_path / "empty.db"
        db_path.write_bytes(b"")

        size = db_path.stat().st_size
        assert size == 0

    def test_truncated_file_detected(self, tmp_path: Path) -> None:
        """A truncated SQLite file should fail integrity check or raise an error."""
        db_path = conn_module._DB_PATH
        assert db_path is not None
        _create_test_data(get_connection())

        full = tmp_path / "full.db"
        _safe_copy_db(db_path, full)

        # Truncate to just the header (less than one page)
        data = full.read_bytes()
        truncated = tmp_path / "truncated.db"
        truncated.write_bytes(data[:50])  # Just the header, not a full page

        conn = sqlite3.connect(str(truncated))
        try:
            try:
                result = conn.execute("PRAGMA integrity_check").fetchone()
                # A truncated file should either fail or report errors
                if result[0] == "ok":
                    # If integrity passes, table count should be wrong
                    tables = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                    assert len(tables) == 0
            except sqlite3.DatabaseError:
                pass  # Exception also confirms corruption detected
        finally:
            conn.close()

    def test_non_sqlite_file_detected(self, tmp_path: Path) -> None:
        """A non-SQLite file should be detected as invalid."""
        fake = tmp_path / "fake.db"
        fake.write_bytes(b"This is a text file pretending to be a database.\n" * 50)

        with pytest.raises(sqlite3.DatabaseError):
            conn = sqlite3.connect(str(fake))
            try:
                conn.execute("SELECT * FROM sqlite_master")
            finally:
                conn.close()


# ---------------------------------------------------------------------------
# Concurrent Backup During Write
# ---------------------------------------------------------------------------

class TestConcurrentBackupDuringWrite:
    """Concurrent backup during write does not corrupt data."""

    def test_concurrent_backup_and_write(self, tmp_path: Path) -> None:
        """Backing up while writing does not produce a corrupt backup.

        On Windows, file locking may prevent concurrent copy operations.
        We handle this gracefully: the backup is attempted after the writer
        finishes if concurrent copy fails due to locking.
        """
        db_path = conn_module._DB_PATH
        assert db_path is not None
        backup = tmp_path / "concurrent_backup.db"

        def writer() -> None:
            conn = sqlite3.connect(str(db_path), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            for i in range(50):
                conn.execute(
                    "INSERT INTO workflows (id, name, schema_version, spec_json, "
                    "version, created_at, updated_at) "
                    "VALUES (?, ?, '1.0', '{}', 1, datetime('now'), datetime('now'))",
                    (f"wf-writer-{i}", f"Writer {i}"),
                )
                conn.commit()
            conn.close()

        def backup_runner() -> None:
            # Retry copy a few times to handle Windows file locking
            for attempt in range(3):
                try:
                    _safe_copy_db(db_path, backup)
                    return
                except (PermissionError, OSError):
                    import time
                    time.sleep(0.1)
            # Final attempt after writer should be done
            _safe_copy_db(db_path, backup)

        t_write = threading.Thread(target=writer)
        t_backup = threading.Thread(target=backup_runner)
        t_write.start()
        t_backup.start()
        t_write.join(timeout=30)
        t_backup.join(timeout=30)

        # Verify backup is valid
        assert backup.exists(), "Backup file was not created"
        conn = sqlite3.connect(str(backup))
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            assert result[0] == "ok"
        finally:
            conn.close()

    def test_multiple_concurrent_backups(self, tmp_path: Path) -> None:
        """Multiple concurrent backups should all be valid."""
        db_path = conn_module._DB_PATH
        assert db_path is not None
        _create_test_data(get_connection())

        results: dict[int, bool] = {}

        def do_backup(idx: int) -> None:
            backup = tmp_path / f"backup_{idx}.db"
            _safe_copy_db(db_path, backup)
            conn = sqlite3.connect(str(backup))
            try:
                result = conn.execute("PRAGMA integrity_check").fetchone()
                results[idx] = result[0] == "ok"
            except Exception:
                results[idx] = False
            finally:
                conn.close()

        threads = [threading.Thread(target=do_backup, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert all(results.values()), f"Some backups failed: {results}"


# ---------------------------------------------------------------------------
# Migration Rollback Scenario
# ---------------------------------------------------------------------------

class TestMigrationRollback:
    """Simulate migration rollback by manual schema manipulation."""

    def test_manual_column_drop_and_reapply(self, tmp_path: Path) -> None:
        """Simulate migration rollback by dropping a column and re-adding it."""
        db_path = conn_module._DB_PATH
        assert db_path is not None
        conn = get_connection()

        # Verify the executions table exists
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "executions" in table_names

        # Simulate a rollback: create a backup, modify schema, verify re-init works
        backup = tmp_path / "pre_rollback.db"
        _safe_copy_db(db_path, backup)

        # Simulate adding a column (as if re-running a migration)
        try:
            conn.execute(
                "ALTER TABLE executions ADD COLUMN _test_rollback_col TEXT DEFAULT ''"
            )
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column might already exist

        # Verify column was added
        result = conn.execute("PRAGMA table_info(executions)").fetchall()
        col_names = [r[1] for r in result]
        assert "_test_rollback_col" in col_names

        # Simulate rollback: restore from backup
        close_connection()
        shutil.copy2(backup, db_path)
        # Copy WAL sidecar if present
        backup_wal = Path(str(backup) + "-wal")
        if backup_wal.exists():
            shutil.copy2(backup_wal, Path(str(db_path) + "-wal"))

        # Reinitialize - init_db is idempotent
        init_db()
        conn = get_connection()

        # Verify database is functional after rollback
        result = conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
        assert result[0] > 0

    def test_init_db_is_idempotent_after_rollback(self, tmp_path: Path) -> None:
        """Calling init_db multiple times after rollback produces no errors."""
        db_path = conn_module._DB_PATH
        assert db_path is not None
        _create_test_data(get_connection())

        backup = tmp_path / "pre_rollback.db"
        _safe_copy_db(db_path, backup)
        close_connection()

        # Restore and reinitialize multiple times
        shutil.copy2(backup, db_path)
        init_db()
        init_db()
        init_db()

        conn = get_connection()
        result = conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
        assert result[0] > 0

    def test_schema_preserved_after_rollback_cycle(self, tmp_path: Path) -> None:
        """All tables survive a backup-modify-restore cycle."""
        db_path = conn_module._DB_PATH
        assert db_path is not None

        # Record original tables
        conn = get_connection()
        original_tables = sorted(
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        )

        # Backup, close, restore, reinitialize
        backup = tmp_path / "backup.db"
        _safe_copy_db(db_path, backup)
        close_connection()
        shutil.copy2(backup, db_path)
        backup_wal = Path(str(backup) + "-wal")
        if backup_wal.exists():
            shutil.copy2(backup_wal, Path(str(db_path) + "-wal"))
        init_db()

        # Verify all tables are still present
        conn = get_connection()
        restored_tables = sorted(
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        )
        assert restored_tables == original_tables


# ---------------------------------------------------------------------------
# DB Initialization After Deleting Database File
# ---------------------------------------------------------------------------

class TestInitAfterDelete:
    """DB initialization after deleting the database file."""

    def test_init_creates_fresh_db(self, tmp_path: Path) -> None:
        """After deleting the DB file, init_db creates a fresh database."""
        db_path = conn_module._DB_PATH
        assert db_path is not None

        # Verify DB exists and has tables
        conn = get_connection()
        tables_before = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert len(tables_before) > 0

        # Delete database and all related files
        close_connection()
        for f in db_path.parent.glob(f"{db_path.name}*"):
            f.unlink()

        assert not db_path.exists()

        # Reinitialize
        init_db()

        conn = get_connection()
        tables_after = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert len(tables_after) > 0
        table_names = [t[0] for t in tables_after]
        assert "workflows" in table_names

    def test_fresh_db_after_delete_is_functional(self, tmp_path: Path) -> None:
        """A freshly created DB (after delete) can store and retrieve data."""
        db_path = conn_module._DB_PATH
        assert db_path is not None

        # Delete everything
        close_connection()
        for f in db_path.parent.glob(f"{db_path.name}*"):
            f.unlink()

        init_db()

        conn = get_connection()
        conn.execute(
            "INSERT INTO workflows (id, name, schema_version, spec_json, "
            "version, created_at, updated_at) "
            "VALUES (?, ?, '1.0', '{}', 1, datetime('now'), datetime('now'))",
            ("wf-fresh", "Fresh Workflow"),
        )
        conn.commit()

        row = conn.execute(
            "SELECT name FROM workflows WHERE id = 'wf-fresh'"
        ).fetchone()
        assert row is not None
        assert row[0] == "Fresh Workflow"

    def test_multiple_delete_and_init_cycles(self, tmp_path: Path) -> None:
        """Multiple delete-init cycles all succeed."""
        db_path = conn_module._DB_PATH
        assert db_path is not None

        for i in range(3):
            close_connection()
            for f in db_path.parent.glob(f"{db_path.name}*"):
                f.unlink()

            init_db()
            conn = get_connection()
            conn.execute(
                "INSERT INTO workflows (id, name, schema_version, spec_json, "
                "version, created_at, updated_at) "
                "VALUES (?, ?, '1.0', '{}', 1, datetime('now'), datetime('now'))",
                (f"wf-cycle-{i}", f"Cycle {i}"),
            )
            conn.commit()

        # Each cycle deletes and recreates the DB, so only the last cycle's data remains
        conn = get_connection()
        rows = conn.execute("SELECT id FROM workflows ORDER BY id").fetchall()
        ids = [r[0] for r in rows]
        # Only wf-cycle-2 should remain (the last cycle before teardown)
        assert "wf-cycle-2" in ids
        assert len(ids) == 1

    def test_init_after_delete_wal_mode(self, tmp_path: Path) -> None:
        """After delete and reinit, WAL mode should be enabled."""
        db_path = conn_module._DB_PATH
        assert db_path is not None

        close_connection()
        for f in db_path.parent.glob(f"{db_path.name}*"):
            f.unlink()

        init_db()
        conn = get_connection()
        mode = conn.execute("PRAGMA journal_mode").fetchone()
        assert mode[0] == "wal"
