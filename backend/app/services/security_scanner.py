"""Dedicated security scanner for detecting secrets and sensitive data.

Expanded from the original ``scan_for_secrets`` in ``scene_exporter.py`` to
cover a wider range of secret categories with proper severity levels.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Sequence


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class SecurityFinding:
    """A single detected security issue."""
    path: str
    line: int
    category: str
    severity: Severity
    matched_text: str
    context: str


# ---------------------------------------------------------------------------
# Pattern definitions -- (compiled_re, category, severity)
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[re.Pattern[str], str, Severity]] = [
    # 1. AWS keys
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws_key", Severity.ERROR),
    # 2. GCP keys
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "gcp_key", Severity.ERROR),
    # 2b. Stripe / generic prefixed keys (sk-..., pk-..., sk_...)
    (re.compile(r"(?:sk|pk|rk)[-_][A-Za-z0-9]{16,}"), "api_key", Severity.ERROR),
    # 3. API tokens / secrets / passwords
    (
        re.compile(
            r"(?:token|api_key|apikey|secret|password|credential)"
            r"[\s]*[=:]\s*['\"]?[A-Za-z0-9_\-]{16,}['\"]?",
            re.IGNORECASE,
        ),
        "api_token",
        Severity.WARNING,
    ),
    # 4. Private keys
    (
        re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
        "private_key",
        Severity.CRITICAL,
    ),
    # 5. Connection strings
    (
        re.compile(r"(?:mongodb|mysql|postgres|redis|amqp)://[^\s]+"),
        "connection_string",
        Severity.CRITICAL,
    ),
    # 6. JWT tokens
    (
        re.compile(r"eyJ[A-Za-z0-9_\-]*\.eyJ[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*"),
        "jwt_token",
        Severity.WARNING,
    ),
    # 7. Hex tokens (high entropy -- 32+ hex chars)
    (
        re.compile(r"[0-9a-fA-F]{32,}"),
        "hex_token",
        Severity.WARNING,
    ),
]

# Keep a quick lookup set for quick exclusions if needed in the future.
CRITICAL_CATEGORIES = {p[1] for p in _PATTERNS if p[2] == Severity.CRITICAL}
ERROR_CATEGORIES = {p[1] for p in _PATTERNS if p[2] == Severity.ERROR}


# ---------------------------------------------------------------------------
# Core scanning helpers
# ---------------------------------------------------------------------------

def _context_lines(text: str, start: int, end: int) -> str:
    """Return a short snippet around the match for human review."""
    snippet = text[max(0, start - 40): end + 40]
    return snippet.replace("\n", " ").strip()


def scan_text(text: str, filename: str = "<input>") -> list[SecurityFinding]:
    """Scan *text* for secrets and return all findings.

    Parameters
    ----------
    text:
        Arbitrary text content to scan.
    filename:
        Label used in the ``path`` field of each finding (cosmetic).
    """
    findings: list[SecurityFinding] = []
    for pattern, category, severity in _PATTERNS:
        for match in pattern.finditer(text):
            # Compute line number
            line_number = text.count("\n", 0, match.start()) + 1
            context = _context_lines(text, match.start(), match.end())
            findings.append(SecurityFinding(
                path=filename,
                line=line_number,
                category=category,
                severity=severity,
                matched_text=match.group(),
                context=context,
            ))
    return findings


def scan_file(filepath: str | Path) -> list[SecurityFinding]:
    """Read and scan a single file for secrets."""
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_text(text, filename=str(path))


def scan_directory(
    dirpath: str | Path,
    extensions: Sequence[str] = (".py", ".ts", ".tsx", ".js", ".jsx", ".env", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini"),
) -> list[SecurityFinding]:
    """Recursively scan all matching files in *dirpath*.

    Parameters
    ----------
    dirpath:
        Root directory to scan.
    extensions:
        File extensions to include (case-insensitive).  Dot-prefixed.
    """
    root = Path(dirpath)
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    norm_exts = {e.lower() for e in extensions}
    findings: list[SecurityFinding] = []

    for dirpath_str, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            if Path(fname).suffix.lower() not in norm_exts:
                continue
            fpath = Path(dirpath_str) / fname
            findings.extend(scan_file(fpath))

    return findings


# ---------------------------------------------------------------------------
# Convenience: backward-compatible wrapper used by scene_exporter
# ---------------------------------------------------------------------------

def scan_for_secrets(text: str) -> list[dict]:
    """Lightweight wrapper that returns dicts matching the old ``SecurityIssue`` schema.

    This keeps ``scene_exporter.scan_for_secrets`` working after the refactor
    without requiring it to import pydantic models.
    """
    findings = scan_text(text, filename="<export>")
    return [
        {
            "severity": f.severity.value if f.severity == Severity.ERROR else "error",
            "code": f.category.upper(),
            "message": f"Detected potential {f.category} at line {f.line}",
            "field": "text",
        }
        for f in findings
        if f.severity in (Severity.CRITICAL, Severity.ERROR, Severity.WARNING)
    ]
