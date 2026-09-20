"""Tests for backend.app.services.security_scanner."""

from __future__ import annotations

import os
import tempfile
import textwrap
from pathlib import Path

import pytest

from backend.app.services.security_scanner import (
    Severity,
    SecurityFinding,
    scan_text,
    scan_file,
    scan_directory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _findings_of_category(findings: list[SecurityFinding], category: str) -> list[SecurityFinding]:
    return [f for f in findings if f.category == category]


def _findings_of_severity(findings: list[SecurityFinding], severity: Severity) -> list[SecurityFinding]:
    return [f for f in findings if f.severity == severity]


# ---------------------------------------------------------------------------
# Pattern detection tests
# ---------------------------------------------------------------------------

class TestAWSDetection:
    def test_aws_access_key_detected(self):
        text = "aws_key = AKIAIOSFODNN7EXAMPLE"
        findings = scan_text(text)
        cats = _findings_of_category(findings, "aws_key")
        assert len(cats) >= 1
        assert cats[0].severity == Severity.ERROR

    def test_aws_key_in_variable(self):
        text = 'ACCESS_KEY="AKIA1234567890ABCDEF"'
        findings = scan_text(text)
        assert len(_findings_of_category(findings, "aws_key")) == 1


class TestGCPDetection:
    def test_gcp_api_key_detected(self):
        text = "gcp_key = AIzaSyA1234567890abcdefghijklmnopqrstuv"
        findings = scan_text(text)
        cats = _findings_of_category(findings, "gcp_key")
        assert len(cats) >= 1
        assert cats[0].severity == Severity.ERROR


class TestAPITokenDetection:
    def test_api_key_assignment(self):
        text = 'api_key = "supersecrettoken12345678"'
        findings = scan_text(text)
        cats = _findings_of_category(findings, "api_token")
        assert len(cats) >= 1

    def test_secret_password(self):
        text = 'password = "mysecretpassword1234"'
        findings = scan_text(text)
        cats = _findings_of_category(findings, "api_token")
        assert len(cats) >= 1

    def test_token_with_equals(self):
        text = 'token: "abcdefghij1234567890xyz"'
        findings = scan_text(text)
        cats = _findings_of_category(findings, "api_token")
        assert len(cats) >= 1

    def test_credential_pattern(self):
        text = 'credential = "my_long_credential_value_1234"'
        findings = scan_text(text)
        cats = _findings_of_category(findings, "api_token")
        assert len(cats) >= 1


class TestPrivateKeyDetection:
    def test_rsa_private_key(self):
        text = "-----BEGIN RSA PRIVATE KEY-----"
        findings = scan_text(text)
        cats = _findings_of_category(findings, "private_key")
        assert len(cats) >= 1
        assert cats[0].severity == Severity.CRITICAL

    def test_ec_private_key(self):
        text = "-----BEGIN EC PRIVATE KEY-----"
        findings = scan_text(text)
        cats = _findings_of_category(findings, "private_key")
        assert len(cats) >= 1
        assert cats[0].severity == Severity.CRITICAL

    def test_generic_private_key(self):
        text = "-----BEGIN PRIVATE KEY-----"
        findings = scan_text(text)
        cats = _findings_of_category(findings, "private_key")
        assert len(cats) >= 1


class TestConnectionStringDetection:
    def test_mongodb_uri(self):
        text = 'MONGO_URL = "mongodb://user:pass@host:27017/db"'
        findings = scan_text(text)
        cats = _findings_of_category(findings, "connection_string")
        assert len(cats) >= 1
        assert cats[0].severity == Severity.CRITICAL

    def test_postgres_uri(self):
        text = "DATABASE_URL=postgres://admin:secret@db.example.com:5432/mydb"
        findings = scan_text(text)
        cats = _findings_of_category(findings, "connection_string")
        assert len(cats) >= 1

    def test_redis_uri(self):
        text = 'REDIS_URL="redis://:password@redis-host:6379/0"'
        findings = scan_text(text)
        cats = _findings_of_category(findings, "connection_string")
        assert len(cats) >= 1

    def test_mysql_uri(self):
        text = "DATABASE=mysql://root:pass123@localhost:3306/testdb"
        findings = scan_text(text)
        cats = _findings_of_category(findings, "connection_string")
        assert len(cats) >= 1

    def test_amqp_uri(self):
        text = "RABBITMQ_URL=amqp://guest:guest@localhost:5672/"
        findings = scan_text(text)
        cats = _findings_of_category(findings, "connection_string")
        assert len(cats) >= 1


class TestJWTDetection:
    def test_jwt_token_detected(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123def456ghi789jkl012mno345pqr678"
        text = f"Bearer {jwt}"
        findings = scan_text(text)
        cats = _findings_of_category(findings, "jwt_token")
        assert len(cats) >= 1


class TestHexTokenDetection:
    def test_long_hex_string(self):
        text = "session_token = a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        findings = scan_text(text)
        cats = _findings_of_category(findings, "hex_token")
        assert len(cats) >= 1

    def test_short_hex_not_flagged(self):
        """Hex strings shorter than 32 chars should not be flagged."""
        text = "hash = abcdef1234567890"
        findings = scan_text(text)
        cats = _findings_of_category(findings, "hex_token")
        assert len(cats) == 0


# ---------------------------------------------------------------------------
# Clean text tests
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_empty_string(self):
        assert scan_text("") == []

    def test_normal_code_no_findings(self):
        code = textwrap.dedent("""\
            def calculate_sum(a: int, b: int) -> int:
                return a + b

            result = calculate_sum(10, 20)
        """)
        findings = scan_text(code)
        assert findings == []

    def test_english_prose_no_findings(self):
        prose = (
            "The quick brown fox jumps over the lazy dog. "
            "This is a simple sentence with no secrets."
        )
        assert scan_text(prose) == []

    def test_python_import_no_false_positive(self):
        code = "from pathlib import Path\nimport os\nprint('hello')"
        assert scan_text(code) == []


# ---------------------------------------------------------------------------
# Severity level tests
# ---------------------------------------------------------------------------

class TestSeverityLevels:
    def test_private_key_is_critical(self):
        findings = scan_text("-----BEGIN PRIVATE KEY-----")
        assert _findings_of_severity(findings, Severity.CRITICAL)

    def test_connection_string_is_critical(self):
        findings = scan_text('url = "postgres://u:p@host/db"')
        assert _findings_of_severity(findings, Severity.CRITICAL)

    def test_aws_key_is_error(self):
        findings = scan_text("AKIAIOSFODNN7EXAMPLE12")
        sevs = {f.severity for f in _findings_of_category(findings, "aws_key")}
        assert Severity.ERROR in sevs

    def test_gcp_key_is_error(self):
        findings = scan_text("AIzaSyA1234567890abcdefghijklmnopqrstuv")
        sevs = {f.severity for f in _findings_of_category(findings, "gcp_key")}
        assert Severity.ERROR in sevs

    def test_api_token_is_warning(self):
        findings = scan_text('api_key = "long_token_value_here_123456"')
        sevs = {f.severity for f in _findings_of_category(findings, "api_token")}
        assert Severity.WARNING in sevs

    def test_hex_token_is_warning(self):
        findings = scan_text("val = " + "ab" * 20)  # 40-char hex
        sevs = {f.severity for f in _findings_of_category(findings, "hex_token")}
        assert Severity.WARNING in sevs


# ---------------------------------------------------------------------------
# scan_file tests
# ---------------------------------------------------------------------------

class TestScanFile:
    def test_scan_file_with_secret(self, tmp_path: Path):
        secret_file = tmp_path / "config.py"
        secret_file.write_text('AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"')
        findings = scan_file(secret_file)
        assert len(findings) >= 1
        assert findings[0].path == str(secret_file)

    def test_scan_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            scan_file("/nonexistent/path/does_not_exist.py")

    def test_scan_file_clean(self, tmp_path: Path):
        clean_file = tmp_path / "utils.py"
        clean_file.write_text("x = 42\nprint(x)")
        findings = scan_file(clean_file)
        assert findings == []


# ---------------------------------------------------------------------------
# scan_directory tests
# ---------------------------------------------------------------------------

class TestScanDirectory:
    def test_scan_directory_finds_secrets(self, tmp_path: Path):
        (tmp_path / "good.py").write_text("x = 1")
        secret = tmp_path / "bad.py"
        secret.write_text('password = "hunter2hunter2hunter2"')
        findings = scan_directory(tmp_path, extensions=(".py",))
        assert any(f.path == str(secret) for f in findings)

    def test_scan_directory_respects_extensions(self, tmp_path: Path):
        (tmp_path / "data.txt").write_text('api_key = "supersecretkey12345678"')
        findings = scan_directory(tmp_path, extensions=(".py",))
        assert findings == []

    def test_scan_directory_not_found(self):
        with pytest.raises(NotADirectoryError):
            scan_directory("/nonexistent/directory")

    def test_scan_directory_multiple_files(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.py").write_text("y = 2")
        (tmp_path / "c.ts").write_text("const z = 3;")
        findings = scan_directory(tmp_path, extensions=(".py", ".ts"))
        assert findings == []


# ---------------------------------------------------------------------------
# False positive rate test
# ---------------------------------------------------------------------------

class TestFalsePositiveRate:
    def test_legitimate_code_no_critical_or_error(self):
        """Real-world-ish code should not trigger critical or error findings."""
        legitimate_code = textwrap.dedent("""\
            import os
            import sys
            from typing import Optional, List

            def connect_to_database(host: str, port: int = 5432) -> object:
                \"\"\"Connect to the database using environment variables.\"\"\"
                url = os.environ.get("DATABASE_URL")
                if not url:
                    raise ValueError("DATABASE_URL not set")
                # TODO: implement connection pooling
                return {"host": host, "port": port}

            class UserManager:
                def __init__(self, db_url: str):
                    self.db_url = db_url

                def authenticate(self, username: str, password: str) -> bool:
                    if username == "admin" and password == "changeme":
                        return True
                    return False

                def get_user(self, user_id: int) -> Optional[dict]:
                    return {"id": user_id, "name": "Test User"}

            if __name__ == "__main__":
                mgr = connect_to_database("localhost")
                print(mgr)
        """)
        findings = scan_text(legitimate_code)
        critical_or_error = [
            f for f in findings if f.severity in (Severity.CRITICAL, Severity.ERROR)
        ]
        # Allow zero critical/error findings from legitimate code
        assert len(critical_or_error) == 0, (
            f"Legitimate code produced {len(critical_or_error)} critical/error findings: "
            + ", ".join(f"{f.category} at line {f.line}" for f in critical_or_error)
        )

    def test_typedef_no_false_positive(self):
        """Type annotations and function signatures should not trigger."""
        code = textwrap.dedent("""\
            def process(
                token: str,
                api_key: str = "",
                secret: str = "",
            ) -> dict:
                return {"token": token}
        """)
        findings = scan_text(code)
        critical_or_error = [
            f for f in findings if f.severity in (Severity.CRITICAL, Severity.ERROR)
        ]
        assert len(critical_or_error) == 0


# ---------------------------------------------------------------------------
# Integration: backward compat with scene_exporter
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_import_from_scene_exporter(self):
        """scan_for_secrets is still importable from scene_exporter."""
        from backend.app.schemas.scene_exporter import scan_for_secrets, SecurityIssue
        issues = scan_for_secrets('api_key = "my_secret_api_key_value"')
        assert isinstance(issues, list)
        assert len(issues) > 0
        # Each item should be a SecurityIssue pydantic model
        first = issues[0]
        assert isinstance(first, SecurityIssue)
        assert first.severity
        assert first.code
        assert first.message

    def test_scan_bundle_security_intact(self):
        """scan_bundle_security still works after the refactor."""
        from backend.app.schemas.scene_exporter import scan_bundle_security
        from backend.app.schemas.scene_bundle import ScenePromptBundle, SceneEntry, SceneImagePrompt, SceneVideoPrompt

        bundle = ScenePromptBundle(
            storyboard_id="test",
            workflow_id="test",
            execution_id="test",
            title="Clean bundle",
            scenes=[
                SceneEntry(
                    scene_id="s1",
                    index=1,
                    title="Scene 1",
                    narration="Hello world",
                    image=SceneImagePrompt(prompt="A mountain"),
                    video=SceneVideoPrompt(prompt="Panoramic view"),
                ),
            ],
        )
        issues = scan_bundle_security(bundle)
        assert isinstance(issues, list)
        # Clean bundle should have no error-severity issues
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0
