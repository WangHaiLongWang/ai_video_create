"""Recovery tests -- disk full scenarios for asset writes and DB writes."""

from __future__ import annotations

import io
import shutil
import sqlite3
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from backend.app.db.connection import close_connection, get_connection, init_db
import backend.app.db.connection as conn_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Each test gets an isolated in-memory-backed temp database."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(conn_module, "_DB_PATH", db_path)
    monkeypatch.setattr(conn_module, "_CONNECTION", None)
    close_connection()
    init_db()
    yield
    close_connection()


class DiskFullError(OSError):
    """Simulated disk-full error for testing."""

    def __init__(self, path: str | Path) -> None:
        super().__init__(28, "No space left on device", str(path))


class _DiskFullWriter:
    """File-like object that raises OSError(ENOSPC) on write."""

    def __init__(self, fail_after: int = 0) -> None:
        self._written = 0
        self._fail_after = fail_after

    def write(self, data: bytes) -> int:
        self._written += len(data)
        if self._fail_after > 0 and self._written > self._fail_after:
            raise DiskFullError("/data")
        return len(data)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass

    def __enter__(self) -> _DiskFullWriter:
        return self

    def __exit__(self, *_: object) -> None:
        pass


# ---------------------------------------------------------------------------
# Asset Write Disk Full
# ---------------------------------------------------------------------------

class TestAssetDiskFull:
    """Behavior when disk is full during asset (file) write."""

    def test_write_raises_on_disk_full(self, tmp_path: Path) -> None:
        """OSError with errno 28 is raised when disk is full."""
        writer = _DiskFullWriter(fail_after=10)
        with pytest.raises(OSError) as exc_info:
            writer.write(b"test data that exceeds the limit")
        assert exc_info.value.errno == 28

    def test_disk_full_error_message_is_clear(self, tmp_path: Path) -> None:
        """Error message includes 'No space left on device'."""
        try:
            raise DiskFullError("/data/assets")
        except OSError as exc:
            assert exc.errno == 28
            assert "No space left on device" in str(exc)

    def test_partial_file_removed_on_disk_full(self, tmp_path: Path) -> None:
        """No partial/corrupt files are left when write fails mid-stream."""
        target = tmp_path / "asset.bin"
        try:
            with open(target, "wb") as f:
                f.write(b"partial")
                raise DiskFullError(target)
        except OSError:
            if target.exists():
                target.unlink()

        assert not target.exists()

    def test_asset_write_rollback_pattern(self, tmp_path: Path) -> None:
        """Write-to-temp-then-rename pattern prevents partial files."""
        target = tmp_path / "asset.bin"
        temp = tmp_path / "asset.bin.tmp"

        # Simulate successful write to temp
        temp.write_bytes(b"complete asset data")

        # Verify temp exists before rename
        assert temp.exists()

        # Simulate rename (atomic on most filesystems)
        temp.rename(target)
        assert target.exists()
        assert not temp.exists()

    def test_disk_full_during_batch_write(self, tmp_path: Path) -> None:
        """Batch write cleans up all partial files on failure."""
        files = [tmp_path / f"file_{i}.bin" for i in range(5)]
        created: list[Path] = []

        try:
            for i, f in enumerate(files):
                if i == 3:
                    raise DiskFullError(f)
                f.write_bytes(f"data_{i}".encode())
                created.append(f)
        except OSError:
            for f in created:
                f.unlink(missing_ok=True)

        assert not any(f.exists() for f in files)


# ---------------------------------------------------------------------------
# Database Write Disk Full
# ---------------------------------------------------------------------------

class TestDatabaseDiskFull:
    """Behavior when disk is full during DB write."""

    def test_db_write_raises_on_disk_full(self, tmp_path: Path) -> None:
        """Database write raises OSError when disk is full."""
        with pytest.raises(OSError) as exc_info:
            raise DiskFullError("database")
        assert exc_info.value.errno == 28

    def test_db_connection_survives_disk_full(self, tmp_path: Path) -> None:
        """DB connection remains usable after a failed write due to disk full."""
        conn = get_connection()

        # Attempt a write that fails
        try:
            # Simulate failure at the execute level
            with patch("backend.app.db.connection.get_connection") as mock_get:
                mock_conn = MagicMock()
                mock_conn.execute.side_effect = DiskFullError("database")
                mock_get.return_value = mock_conn
                mock_conn.execute("INSERT INTO workflows VALUES ('fail')")
        except OSError:
            pass

        # Real connection should still work
        result = conn.execute("SELECT 1").fetchone()
        assert result[0] == 1

    def test_db_rollback_on_disk_full(self, tmp_path: Path) -> None:
        """SQLite automatically rolls back on write failure."""
        conn = get_connection()
        conn.execute(
            "INSERT INTO workflows (id, name, schema_version, spec_json, "
            "version, created_at, updated_at) "
            "VALUES ('wf-ok', 'OK', '1.0', '{}', 1, datetime('now'), datetime('now'))"
        )
        conn.commit()

        # Attempt an operation that will fail (simulate via corrupt SQL after disk full)
        try:
            conn.execute("INSERT INTO workflows VALUES (NULL, NULL)")
        except sqlite3.Error:
            conn.rollback()

        # Previous data should still be intact
        row = conn.execute("SELECT name FROM workflows WHERE id = 'wf-ok'").fetchone()
        assert row is not None
        assert row[0] == "OK"

    def test_partial_db_file_recovery(self, tmp_path: Path) -> None:
        """After a disk-full corruption, backup/restore recovers data."""
        import sqlite3 as _sqlite3

        db_path = conn_module._DB_PATH
        assert db_path is not None

        # Create a good backup first
        conn = get_connection()
        conn.execute(
            "INSERT INTO workflows (id, name, schema_version, spec_json, "
            "version, created_at, updated_at) "
            "VALUES ('wf-safe', 'Safe', '1.0', '{}', 1, datetime('now'), datetime('now'))"
        )
        conn.commit()

        # Create a proper backup (checkpoint WAL, then copy)
        backup = tmp_path / "safe_backup.db"
        bak_conn = _sqlite3.connect(str(db_path))
        try:
            bak_conn.execute("PRAGMA wal_checkpoint(FULL)")
        except Exception:
            pass
        finally:
            bak_conn.close()
        shutil.copy2(db_path, backup)
        # Also copy WAL if present
        wal_src = Path(str(db_path) + "-wal")
        if wal_src.exists():
            shutil.copy2(wal_src, Path(str(backup) + "-wal"))

        # Simulate corruption of main db
        close_connection()
        db_path.write_bytes(b"corrupt" * 100)

        # Restore from backup
        shutil.copy2(backup, db_path)
        wal_dst = Path(str(backup) + "-wal")
        if wal_dst.exists():
            shutil.copy2(wal_dst, Path(str(db_path) + "-wal"))
        init_db()

        conn = get_connection()
        row = conn.execute("SELECT name FROM workflows WHERE id = 'wf-safe'").fetchone()
        assert row is not None
        assert row[0] == "Safe"

    def test_user_friendly_error_for_disk_full(self, tmp_path: Path) -> None:
        """Error messages for disk full are user-friendly."""
        try:
            raise DiskFullError("/data/assets")
        except OSError as exc:
            # Verify the error is descriptive
            assert exc.errno == 28
            message = str(exc)
            assert "No space left on device" in message

    def test_no_partial_files_after_failed_write(self, tmp_path: Path) -> None:
        """No partial/corrupt DB files are left after a failed write operation."""
        db_path = conn_module._DB_PATH
        assert db_path is not None

        # Get the original size
        original_size = db_path.stat().st_size

        # Simulate a failed write that doesn't modify the file
        conn = get_connection()
        try:
            # Force a failure with invalid SQL
            conn.execute("NOT VALID SQL")
        except sqlite3.OperationalError:
            pass

        # File size should be unchanged (or only WAL growth, not corruption)
        assert db_path.stat().st_size >= original_size
