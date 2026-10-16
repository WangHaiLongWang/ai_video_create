#!/usr/bin/env python3
"""Create a reproducible, non-secret release manifest with SHA-256 hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "VERSION",
    "package.json",
    "frontend/package.json",
    "frontend/package-lock.json",
    "backend/requirements.txt",
    "backend/constraints.txt",
    "backend/pyproject.toml",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str | None:
    try:
        return subprocess.check_output(("git", *args), cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "release-manifest.json")
    args = parser.parse_args()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    files = {name: sha256(ROOT / name) for name in FILES if (ROOT / name).is_file()}
    payload = {
        "schemaVersion": 1,
        "version": version,
        "gitSha": git_value("rev-parse", "HEAD"),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "files": files,
        "verification": "python scripts/verify-release-metadata.py; sha256sum --check release-manifest.sha256",
    }
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checksum = output.with_suffix(".sha256")
    checksum.write_text(f"{sha256(output)}  {output.name}\n", encoding="utf-8")
    print(f"wrote {output} and {checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
