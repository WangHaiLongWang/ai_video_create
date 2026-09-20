"""Tests for backend.app.services.audit_logger."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from backend.app.services.audit_logger import AuditLogger


@pytest.fixture()
def audit(tmp_path: Path) -> AuditLogger:
    """Return an AuditLogger that writes to a temporary file."""
    log_file = tmp_path / "audit.jsonl"
    return AuditLogger(log_path=log_file)


@pytest.fixture()
def log_file(audit: AuditLogger, tmp_path: Path) -> Path:
    """Return the path to the audit log file."""
    return tmp_path / "audit.jsonl"


class TestLogEvent:
    """Tests for ``log_event``."""

    def test_writes_to_file(self, audit: AuditLogger, log_file: Path) -> None:
        record = audit.log_event(event_type="login_attempt", detail={"user": "alice"})
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8").strip()
        assert content  # non-empty
        parsed = json.loads(content)
        assert parsed["event_type"] == "login_attempt"
        assert parsed["detail"]["user"] == "alice"
        assert parsed["event_id"] == record["event_id"]

    def test_multiple_events(self, audit: AuditLogger, log_file: Path) -> None:
        for i in range(3):
            audit.log_event(event_type=f"event_{i}")
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        for idx, line in enumerate(lines):
            parsed = json.loads(line)
            assert parsed["event_type"] == f"event_{idx}"

    def test_timestamp_is_iso(self, audit: AuditLogger, log_file: Path) -> None:
        audit.log_event(event_type="test")
        parsed = json.loads(log_file.read_text(encoding="utf-8").strip())
        # ISO-8601 datetime string
        assert "T" in parsed["timestamp"]

    def test_default_fields(self, audit: AuditLogger, log_file: Path) -> None:
        audit.log_event(event_type="check")
        parsed = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert parsed["source_ip"] == "unknown"
        assert parsed["severity"] == "info"
        assert parsed["detail"] == {}


class TestLogSecurityEvent:
    """Tests for ``log_security_event``."""

    def test_includes_severity(self, audit: AuditLogger, log_file: Path) -> None:
        record = audit.log_security_event(
            event_type="ssrf_blocked",
            source_ip="10.0.0.1",
            detail={"url": "http://evil.com"},
        )
        parsed = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert parsed["severity"] == "warning"
        assert parsed["source_ip"] == "10.0.0.1"
        assert parsed["detail"]["url"] == "http://evil.com"

    def test_custom_severity(self, audit: AuditLogger, log_file: Path) -> None:
        audit.log_security_event(
            event_type="brute_force", severity="error"
        )
        parsed = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert parsed["severity"] == "error"


class TestLogApiAccess:
    """Tests for ``log_api_access``."""

    def test_writes_api_event(self, audit: AuditLogger, log_file: Path) -> None:
        audit.log_api_access(
            endpoint="/api/workflows",
            source_ip="192.168.1.100",
            detail={"method": "POST"},
        )
        parsed = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert parsed["event_type"] == "api_access"
        assert parsed["endpoint"] == "/api/workflows"


class TestJsonlFormat:
    """Ensure the output is valid JSONL (one JSON object per line)."""

    def test_valid_jsonl(self, audit: AuditLogger, log_file: Path) -> None:
        audit.log_event(event_type="e1")
        audit.log_security_event(event_type="e2")
        audit.log_api_access(endpoint="/x")
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        for line in lines:
            parsed = json.loads(line)  # should not raise
            assert isinstance(parsed, dict)
            assert "event_type" in parsed
            assert "timestamp" in parsed

    def test_invalid_severity_falls_back_to_info(
        self, audit: AuditLogger, log_file: Path
    ) -> None:
        audit.log_event(event_type="test", severity="bogus")
        parsed = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert parsed["severity"] == "info"
