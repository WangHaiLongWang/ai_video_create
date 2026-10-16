import json
from pathlib import Path
import sqlite3
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "db-maintenance.py"


def run(*args: str):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_backup_and_restore_roundtrip_with_checksum(tmp_path):
    database = tmp_path / "active.db"
    backup = tmp_path / "backups" / "ai_video_create_test.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        db.execute("INSERT INTO sample VALUES ('before')")

    result = run("backup", "--database", str(database), "--output", str(backup))
    assert result.returncode == 0, result.stderr
    metadata = json.loads(backup.with_suffix(".db.json").read_text(encoding="utf-8"))
    assert metadata["bytes"] > 0
    assert len(metadata["sha256"]) == 64

    with sqlite3.connect(database) as db:
        db.execute("UPDATE sample SET value = 'after'")
    result = run("restore", "--database", str(database), "--backup", str(backup))
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT value FROM sample").fetchone()[0] == "before"
    assert list(tmp_path.glob("active.db.pre-restore-*"))


def test_restore_rejects_tampered_backup(tmp_path):
    database = tmp_path / "active.db"
    backup = tmp_path / "backup.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    assert run("backup", "--database", str(database), "--output", str(backup)).returncode == 0
    metadata_path = backup.with_suffix(".db.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["sha256"] = "0" * 64
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    result = run("restore", "--database", str(database), "--backup", str(backup))
    assert result.returncode != 0
    assert "checksum mismatch" in result.stderr
