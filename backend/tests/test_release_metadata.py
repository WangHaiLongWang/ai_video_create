from pathlib import Path
import json
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_release_metadata_versions_are_consistent():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify-release-metadata.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_release_manifest_contains_only_expected_dependency_files(tmp_path):
    output = tmp_path / "release-manifest.json"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "release-manifest.py"), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["version"] == (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert "frontend/package-lock.json" in payload["files"]
    assert "backend/constraints.txt" in payload["files"]
    assert output.with_suffix(".sha256").exists()
