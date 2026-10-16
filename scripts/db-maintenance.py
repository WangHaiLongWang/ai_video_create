#!/usr/bin/env python3
"""Safe SQLite backup/restore utility used by release operations."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def integrity(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"database not found: {path}")
    db = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    cursor = db.execute("PRAGMA integrity_check")
    try:
        result = cursor.fetchone()
    finally:
        cursor.close()
        db.close()
    if not result or result[0] != "ok":
        raise SystemExit(f"integrity check failed for {path}: {result}")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def backup(source: Path, output: Path, keep: int | None = None) -> None:
    integrity(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.unlink(missing_ok=True)
    try:
        # SQLite's online backup includes committed WAL pages in one consistent DB.
        src = sqlite3.connect(str(source))
        dst = sqlite3.connect(str(temp))
        try:
            src.backup(dst)
            dst.commit()
        finally:
            # Explicit close is required on Windows before replacing/deleting the
            # temporary file; context-manager exit alone can leave a handle open.
            dst.close()
            src.close()
        integrity(temp)
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)
    metadata = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "source": str(source.resolve()),
        "backup": output.name,
        "sha256": digest(output),
        "bytes": output.stat().st_size,
    }
    output.with_suffix(output.suffix + ".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if keep is not None and keep > 0:
        backups = sorted(output.parent.glob("ai_video_create_*.db"), key=lambda p: p.stat().st_mtime)
        for stale in backups[:-keep]:
            stale.unlink(missing_ok=True)
            stale.with_suffix(stale.suffix + ".json").unlink(missing_ok=True)
    print(json.dumps(metadata, ensure_ascii=False))


def restore(source: Path, target: Path) -> None:
    integrity(source)
    expected_meta = source.with_suffix(source.suffix + ".json")
    if expected_meta.is_file():
        metadata = json.loads(expected_meta.read_text(encoding="utf-8"))
        if metadata.get("sha256") != digest(source):
            raise SystemExit(f"backup checksum mismatch: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        safety = target.with_name(f"{target.name}.pre-restore-{utc_stamp()}")
        backup(target, safety)
        print(f"safety backup: {safety}")
    for suffix in ("-wal", "-shm", "-journal"):
        Path(f"{target}{suffix}").unlink(missing_ok=True)
    # Restore through SQLite rather than replacing an openable path. This is
    # portable on Windows and guarantees a complete transaction-level copy.
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
        dst.commit()
    finally:
        dst.close()
        src.close()
    integrity(target)
    print(f"restored {source} -> {target}; sha256={digest(target)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    backup_cmd = sub.add_parser("backup")
    backup_cmd.add_argument("--database", required=True, type=Path)
    backup_cmd.add_argument("--output", type=Path)
    backup_cmd.add_argument("--backup-dir", type=Path, default=Path("data/backups"))
    backup_cmd.add_argument("--keep", type=int, default=10)
    restore_cmd = sub.add_parser("restore")
    restore_cmd.add_argument("--database", required=True, type=Path)
    restore_cmd.add_argument("--backup", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "backup":
        output = args.output or args.backup_dir / f"ai_video_create_{utc_stamp()}.db"
        backup(args.database.resolve(), output.resolve(), args.keep)
    else:
        restore(args.backup.resolve(), args.database.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
