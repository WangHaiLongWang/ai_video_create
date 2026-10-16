"""Transactional schema migration ledger tests (HARD-201..204)."""

from __future__ import annotations

import sqlite3

import pytest

from backend.app.db.connection import (
    MigrationChecksumError,
    MigrationError,
    apply_migrations,
)


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_applies_once_and_records_checksum(tmp_path):
    (tmp_path / "001_create.sql").write_text(
        "CREATE TABLE sample (id INTEGER PRIMARY KEY);\n", encoding="utf-8"
    )
    conn = _connection()

    assert apply_migrations(conn, tmp_path) == ["001"]
    assert apply_migrations(conn, tmp_path) == []
    row = conn.execute("SELECT * FROM schema_migrations").fetchone()
    assert row["version"] == "001"
    assert len(row["checksum"]) == 64


def test_detects_modified_applied_migration(tmp_path):
    path = tmp_path / "001_create.sql"
    path.write_text("CREATE TABLE sample (id INTEGER);\n", encoding="utf-8")
    conn = _connection()
    apply_migrations(conn, tmp_path)

    path.write_text("CREATE TABLE sample (id TEXT);\n", encoding="utf-8")
    with pytest.raises(MigrationChecksumError):
        apply_migrations(conn, tmp_path)


def test_failed_migration_rolls_back_schema_and_ledger(tmp_path):
    (tmp_path / "001_broken.sql").write_text(
        "CREATE TABLE partial_table (id INTEGER);\n"
        "INSERT INTO missing_table VALUES (1);\n",
        encoding="utf-8",
    )
    conn = _connection()

    with pytest.raises(MigrationError):
        apply_migrations(conn, tmp_path)

    assert conn.execute(
        "SELECT name FROM sqlite_master WHERE name='partial_table'"
    ).fetchone() is None
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 0


def test_adopts_legacy_database_with_duplicate_column(tmp_path):
    conn = _connection()
    conn.execute("CREATE TABLE legacy (id INTEGER, added TEXT)")
    (tmp_path / "001_legacy.sql").write_text(
        "CREATE TABLE IF NOT EXISTS legacy (id INTEGER);\n"
        "ALTER TABLE legacy ADD COLUMN added TEXT;\n",
        encoding="utf-8",
    )

    assert apply_migrations(conn, tmp_path) == ["001"]
    assert apply_migrations(conn, tmp_path) == []


def test_repository_migrations_create_expected_tables(tmp_path):
    from backend.app.db.connection import MIGRATIONS_DIR

    conn = _connection()
    applied = apply_migrations(conn, MIGRATIONS_DIR)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    assert applied[0] == "001"
    assert applied[-1] == "013"
    assert {"workflows", "module_definitions", "agent_traces", "provider_configs", "schema_migrations"} <= tables
