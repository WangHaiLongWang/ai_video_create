#!/usr/bin/env python3
"""Standalone security scanner for CI/CD pipelines.

Wraps ``backend.app.services.security_scanner`` and provides CLI options
for directory selection, output format, and severity filtering.

Usage
-----
    python scripts/security_scan.py \
        --scan-dir backend/app \
        --scan-dir frontend/src \
        --format table \
        --format json \
        --output report.json \
        --severity warning
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve the backend security_scanner module regardless of CWD
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_BACKEND_DIR = _PROJECT_ROOT / "backend"

# Ensure the backend package is importable
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    from app.services.security_scanner import (
        SecurityFinding,
        Severity,
        scan_directory,
        scan_file,
    )
except ImportError as exc:
    print(
        f"ERROR: Cannot import security_scanner module: {exc}\n"
        "Make sure backend/app/services/security_scanner.py exists.",
        file=sys.stderr,
    )
    sys.exit(2)

# ---------------------------------------------------------------------------
# Severity helpers
# ---------------------------------------------------------------------------
_SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.ERROR: 1,
    Severity.WARNING: 2,
}

MIN_SEVERITY: dict[str, Severity] = {
    "critical": Severity.CRITICAL,
    "error": Severity.ERROR,
    "warning": Severity.WARNING,
}


def _passes_severity_filter(finding: SecurityFinding, min_sev: Severity) -> bool:
    return _SEVERITY_ORDER.get(finding.severity, 99) <= _SEVERITY_ORDER.get(min_sev, 99)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _format_table(findings: list[SecurityFinding]) -> str:
    if not findings:
        return "No security findings detected."

    lines: list[str] = []
    header = f"{'SEVERITY':<10} {'CATEGORY':<22} {'FILE':<50} {'LINE':<6} {'MATCH'}"
    lines.append(header)
    lines.append("-" * len(header))

    for f in sorted(findings, key=lambda x: _SEVERITY_ORDER.get(x.severity, 99)):
        truncated = f.matched_text[:40] + ("..." if len(f.matched_text) > 40 else "")
        short_path = _short_path(f.path)
        lines.append(
            f"{f.severity.value.upper():<10} {f.category:<22} {short_path:<50} {f.line:<6} {truncated}"
        )

    return "\n".join(lines)


def _short_path(filepath: str) -> str:
    """Shorten path relative to project root for readability."""
    try:
        p = Path(filepath).resolve()
        rel = p.relative_to(_PROJECT_ROOT)
        return str(rel)
    except ValueError:
        return filepath


def _format_json(findings: list[SecurityFinding]) -> dict:
    by_severity: dict[str, int] = {"critical": 0, "error": 0, "warning": 0}
    by_category: dict[str, int] = {}

    for f in findings:
        by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
        by_category[f.category] = by_category.get(f.category, 0) + 1

    return {
        "total": len(findings),
        "critical_count": by_severity.get("critical", 0),
        "error_count": by_severity.get("error", 0),
        "warning_count": by_severity.get("warning", 0),
        "by_category": by_category,
        "findings": [
            {
                "path": _short_path(f.path),
                "line": f.line,
                "severity": f.severity.value,
                "category": f.category,
                "matched_text": f.matched_text,
                "context": f.context,
            }
            for f in findings
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan source code for secrets and sensitive data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scan-dir",
        action="append",
        default=[],
        help="Directory to scan (can be specified multiple times).",
    )
    parser.add_argument(
        "--scan-file",
        action="append",
        default=[],
        help="Individual file to scan (can be specified multiple times).",
    )
    parser.add_argument(
        "--format",
        dest="formats",
        action="append",
        choices=["table", "json"],
        default=[],
        help="Output format (can be specified multiple times). Default: table.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write JSON output to this file path.",
    )
    parser.add_argument(
        "--severity",
        choices=["critical", "error", "warning"],
        default="warning",
        help="Minimum severity to report (default: warning).",
    )
    args = parser.parse_args(argv)

    if not args.scan_dir and not args.scan_file:
        parser.error("At least one --scan-dir or --scan-file must be provided.")

    if not args.formats:
        args.formats = ["table"]

    min_severity = MIN_SEVERITY[args.severity]
    all_findings: list[SecurityFinding] = []

    # Scan directories
    for d in args.scan_dir:
        dirpath = Path(d)
        if not dirpath.is_absolute():
            dirpath = _PROJECT_ROOT / dirpath
        if not dirpath.is_dir():
            print(f"WARNING: Directory not found, skipping: {d}", file=sys.stderr)
            continue
        findings = scan_directory(str(dirpath))
        all_findings.extend(findings)

    # Scan individual files
    for f in args.scan_file:
        filepath = Path(f)
        if not filepath.is_absolute():
            filepath = _PROJECT_ROOT / filepath
        if not filepath.is_file():
            print(f"WARNING: File not found, skipping: {f}", file=sys.stderr)
            continue
        findings = scan_file(str(filepath))
        all_findings.extend(findings)

    # Apply severity filter
    filtered = [f for f in all_findings if _passes_severity_filter(f, min_severity)]

    # Output
    for fmt in args.formats:
        if fmt == "table":
            print(_format_table(filtered))
        elif fmt == "json":
            json_data = _format_json(filtered)
            if args.output:
                output_path = Path(args.output)
                if not output_path.is_absolute():
                    output_path = _PROJECT_ROOT / output_path
                output_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False))
                print(f"JSON report written to: {output_path}")
            else:
                print(json.dumps(json_data, indent=2, ensure_ascii=False))

    # Summary
    critical = sum(1 for f in filtered if f.severity == Severity.CRITICAL)
    errors = sum(1 for f in filtered if f.severity == Severity.ERROR)
    warnings = sum(1 for f in filtered if f.severity == Severity.WARNING)

    print(f"\n--- Scan complete: {len(filtered)} findings "
          f"({critical} critical, {errors} error, {warnings} warning) ---")

    # Exit code: 1 if critical findings exist (fail CI)
    if critical > 0:
        print("FAILED: Critical security findings detected!", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
