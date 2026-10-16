#!/usr/bin/env python3
"""Verify that release metadata has one canonical version source.

This check is intentionally dependency-free so it can run before installing the
application. It is used by both local RC checks and CI.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path.relative_to(ROOT)}: {exc}")
    return {}


def main() -> int:
    version_path = ROOT / "VERSION"
    version = version_path.read_text(encoding="utf-8").strip()
    if not VERSION_RE.fullmatch(version):
        fail(f"VERSION is not semver: {version!r}")

    root_package = read_json(ROOT / "package.json")
    web_package = read_json(ROOT / "frontend" / "package.json")
    expected = {
        "package.json": root_package.get("version"),
        "frontend/package.json": web_package.get("version"),
        "package-lock.json": read_json(ROOT / "package-lock.json").get("version"),
        "frontend/package-lock.json": read_json(ROOT / "frontend" / "package-lock.json").get("version"),
    }
    for name, value in expected.items():
        if value != version:
            fail(f"{name} version {value!r} != VERSION {version!r}")

    pyproject = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    # PEP 440 spells the same prerelease as 1.0.0rc1 (without a hyphen).
    pep440 = version.replace("-rc.", "rc").replace("-beta.", "b").replace("-alpha.", "a")
    if not re.search(rf'^version\s*=\s*[\"\']{re.escape(pep440)}[\"\']', pyproject, re.MULTILINE):
        fail(f"backend/pyproject.toml version does not match {pep440!r}")

    print(f"[PASS] canonical release version: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
