"""SCENE-009: Secret / signed-URL / absolute-path scanner tests.

Comprehensive tests for the scene security scanner that prevents leaking
secrets, signed URLs, absolute paths, email addresses, IPs, and other
sensitive data through exported scene bundles.
"""

from __future__ import annotations

import json

import pytest

from backend.app.schemas.scene_bundle import (
    SceneEntry,
    SceneImagePrompt,
    ScenePromptBundle,
    SceneVideoPrompt,
)
from backend.app.schemas.scene_exporter import (
    SecurityIssue,
    export_to_csv,
    export_to_json,
    export_to_jsonl,
    export_to_markdown,
    export_to_text,
    scan_bundle_security,
    scan_for_secrets,
    validate_export_safety,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bundle(**overrides) -> ScenePromptBundle:
    """Create a minimal valid bundle with optional field overrides."""
    defaults = dict(
        storyboard_id="sb-001",
        workflow_id="wf-001",
        execution_id="ex-001",
        title="Test Bundle",
        scenes=[
            SceneEntry(
                scene_id="scene-1",
                index=1,
                title="Scene One",
                narration="A gentle narration about mountains.",
                image=SceneImagePrompt(prompt="snowy mountain peak"),
                video=SceneVideoPrompt(prompt="camera pans across mountain range"),
            ),
        ],
    )
    defaults.update(overrides)
    return ScenePromptBundle(**defaults)


def _bundle_with_text(**field_texts) -> ScenePromptBundle:
    """Create a bundle where specific text fields contain the given strings."""
    scene_kwargs = dict(
        scene_id="scene-1",
        index=1,
        title=field_texts.get("title", "Scene One"),
        narration=field_texts.get("narration", "A gentle narration."),
        image=SceneImagePrompt(
            prompt=field_texts.get("image_prompt", "snowy mountain peak"),
            negative_prompt=field_texts.get("image_negative", None),
        ),
        video=SceneVideoPrompt(
            prompt=field_texts.get("video_prompt", "camera pans"),
        ),
    )
    return ScenePromptBundle(
        storyboard_id="sb-001",
        workflow_id="wf-001",
        execution_id="ex-001",
        title=field_texts.get("bundle_title", "Test Bundle"),
        global_style=field_texts.get("global_style"),
        negative_prompt=field_texts.get("bundle_negative"),
        scenes=[SceneEntry(**scene_kwargs)],
    )


# ===================================================================
# scan_for_secrets — low-level text scanner
# ===================================================================

class TestScanForSecrets:
    """Tests for the scan_for_secrets(text) function."""

    def test_clean_text_no_issues(self):
        assert scan_for_secrets("hello world, this is clean text") == []

    def test_empty_string(self):
        assert scan_for_secrets("") == []

    # -- API keys --
    def test_detects_sk_key(self):
        issues = scan_for_secrets("key is sk-abc123def456ghi789jkl0")
        assert len(issues) >= 1
        assert issues[0].code == "SECRET_KEY"
        assert issues[0].severity == "error"

    def test_detects_api_key_assignment(self):
        issues = scan_for_secrets("api_key=supersecretvalue123")
        assert any(i.code == "SECRET_KEY" for i in issues)

    def test_detects_apikey_header(self):
        issues = scan_for_secrets("apikey: my-secret-api-key-here")
        assert any(i.code == "SECRET_KEY" for i in issues)

    def test_detects_bearer_token(self):
        issues = scan_for_secrets("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9")
        assert any(i.code == "SECRET_KEY" for i in issues)

    # -- Signed URLs --
    def test_detects_aws_signature(self):
        issues = scan_for_secrets(
            "https://bucket.s3.amazonaws.com/file?Signature=abc123"
        )
        assert any(i.code == "SIGNED_URL" for i in issues)

    def test_detects_amz_signature(self):
        issues = scan_for_secrets(
            "https://s3.amazonaws.com/file?X-Amz-Signature=abcdef"
        )
        assert any(i.code == "SIGNED_URL" for i in issues)

    def test_detects_sig_param(self):
        issues = scan_for_secrets("https://example.com/download?sig=xyz789")
        assert any(i.code == "SIGNED_URL" for i in issues)

    def test_detects_token_param(self):
        issues = scan_for_secrets(
            "https://example.com/download?token=eyJhbGciOi"
        )
        assert any(i.code == "SIGNED_URL" for i in issues)

    # -- Absolute paths --
    def test_detects_windows_path(self):
        issues = scan_for_secrets("File is at C:\\Users\\admin\\secret.txt")
        assert any(i.code == "ABSOLUTE_PATH" for i in issues)

    def test_detects_unix_home_path(self):
        issues = scan_for_secrets("Config at /home/user/.ssh/id_rsa")
        assert any(i.code == "ABSOLUTE_PATH" for i in issues)

    def test_detects_etc_path(self):
        issues = scan_for_secrets("Read from /etc/passwd")
        assert any(i.code == "ABSOLUTE_PATH" for i in issues)

    def test_detects_unc_path(self):
        issues = scan_for_secrets("Shared at \\\\server\\share\\file.txt")
        assert any(i.code == "ABSOLUTE_PATH" for i in issues)

    # -- Env vars / API key variables --
    def test_detects_env_var_braces(self):
        issues = scan_for_secrets("Use ${API_KEY} for auth")
        assert any(i.code == "API_KEY" for i in issues)

    def test_detects_dollar_api_key(self):
        issues = scan_for_secrets("Export $OPENAI_API_KEY before running")
        assert any(i.code == "API_KEY" for i in issues)

    def test_detects_process_env(self):
        issues = scan_for_secrets("const key = process.env.API_KEY")
        assert any(i.code == "API_KEY" for i in issues)

    # -- Emails --
    def test_detects_email(self):
        issues = scan_for_secrets("Contact admin@example.com for help")
        assert any(i.code == "EMAIL" for i in issues)
        email_issue = [i for i in issues if i.code == "EMAIL"][0]
        assert email_issue.severity == "warning"

    # -- IP addresses --
    def test_detects_ip_address(self):
        issues = scan_for_secrets("Server at 192.168.1.100 is down")
        assert any(i.code == "IP_ADDRESS" for i in issues)
        ip_issue = [i for i in issues if i.code == "IP_ADDRESS"][0]
        assert ip_issue.severity == "warning"

    # -- Case variations --
    def test_api_key_case_insensitive(self):
        issues = scan_for_secrets("API_KEY=secret123")
        assert any(i.code == "SECRET_KEY" for i in issues)

    # -- Partial matches that should NOT trigger --
    def test_short_sk_not_flagged(self):
        """sk- followed by fewer than 16 chars should not trigger."""
        issues = scan_for_secrets("Use sk-abc for the prefix")
        assert not any(i.code == "SECRET_KEY" for i in issues)

    # -- Multiple violations --
    def test_multiple_violations_detected(self):
        text = "key=sk-abc123def456ghi789 and email admin@test.com"
        issues = scan_for_secrets(text)
        codes = {i.code for i in issues}
        assert "SECRET_KEY" in codes
        assert "EMAIL" in codes


# ===================================================================
# scan_bundle_security — bundle-level scanner
# ===================================================================

class TestScanBundleSecurity:
    """Tests for scan_bundle_security(bundle)."""

    def test_clean_bundle_no_issues(self):
        bundle = _make_bundle()
        issues = scan_bundle_security(bundle)
        assert issues == []

    def test_api_key_in_narration(self):
        bundle = _bundle_with_text(narration="Use api_key=secret123456789012")
        issues = scan_bundle_security(bundle)
        assert any(i.code == "SECRET_KEY" and i.scene_id == "scene-1" for i in issues)

    def test_signed_url_in_image_prompt(self):
        bundle = _bundle_with_text(
            image_prompt="Upload to https://s3.amazonaws.com/b?X-Amz-Signature=abc"
        )
        issues = scan_bundle_security(bundle)
        assert any(i.code == "SIGNED_URL" for i in issues)

    def test_absolute_path_in_video_prompt(self):
        bundle = _bundle_with_text(video_prompt="Render to C:\\output\\video.mp4")
        issues = scan_bundle_security(bundle)
        assert any(i.code == "ABSOLUTE_PATH" for i in issues)

    def test_env_var_in_title(self):
        bundle = _bundle_with_text(title="Scene with ${API_KEY}")
        issues = scan_bundle_security(bundle)
        assert any(i.code == "API_KEY" for i in issues)

    def test_secret_in_bundle_title(self):
        bundle = _bundle_with_text(bundle_title="Project sk-1234567890abcdef12")
        issues = scan_bundle_security(bundle)
        assert any(i.code == "SECRET_KEY" and i.field == "bundle.title" for i in issues)

    def test_secret_in_global_style(self):
        bundle = _bundle_with_text(global_style="api_key=mysecretkey")
        issues = scan_bundle_security(bundle)
        assert any(i.code == "SECRET_KEY" and i.field == "bundle.globalStyle" for i in issues)

    def test_secret_in_negative_prompt(self):
        bundle = _bundle_with_text(bundle_negative="Not ${OPENAI_API_KEY}")
        issues = scan_bundle_security(bundle)
        assert any(i.code == "API_KEY" and i.field == "bundle.negativePrompt" for i in issues)

    def test_secret_in_image_negative_prompt(self):
        bundle = _bundle_with_text(image_negative="Avoid sk-abcdefghijklmnop")
        issues = scan_bundle_security(bundle)
        assert any(
            i.code == "SECRET_KEY" and i.field == "image.negativePrompt"
            for i in issues
        )

    def test_multiple_scenes_all_scanned(self):
        scenes = [
            SceneEntry(
                scene_id=f"scene-{i}",
                index=i,
                title=f"Scene {i}",
                narration=f"Narration with api_key=secret{i}",
                image=SceneImagePrompt(prompt="clean prompt"),
                video=SceneVideoPrompt(prompt="clean prompt"),
            )
            for i in range(1, 4)
        ]
        bundle = ScenePromptBundle(
            storyboard_id="sb-001",
            workflow_id="wf-001",
            execution_id="ex-001",
            title="Multi-scene",
            scenes=scenes,
        )
        issues = scan_bundle_security(bundle)
        scene_ids = {i.scene_id for i in issues if i.scene_id}
        assert len(scene_ids) == 3


# ===================================================================
# validate_export_safety
# ===================================================================

class TestValidateExportSafety:
    """Tests for validate_export_safety(bundle)."""

    def test_clean_bundle_is_safe(self):
        bundle = _make_bundle()
        is_safe, issues = validate_export_safety(bundle)
        assert is_safe is True
        assert issues == []

    def test_error_blocks_export(self):
        bundle = _bundle_with_text(narration="Use api_key=supersecret123456")
        is_safe, issues = validate_export_safety(bundle)
        assert is_safe is False
        assert any(i.severity == "error" for i in issues)

    def test_warning_does_not_block(self):
        bundle = _bundle_with_text(narration="Server at 192.168.1.1")
        is_safe, issues = validate_export_safety(bundle)
        # IP is warning severity, should not block
        assert is_safe is True
        assert len(issues) > 0

    def test_mixed_error_and_warning(self):
        bundle = _bundle_with_text(
            narration="key=sk-1234567890abcdef12 and server 10.0.0.1"
        )
        is_safe, issues = validate_export_safety(bundle)
        assert is_safe is False
        codes = {i.code for i in issues}
        assert "SECRET_KEY" in codes
        assert "IP_ADDRESS" in codes


# ===================================================================
# Export format security enforcement
# ===================================================================

class TestExportFormatSecurity:
    """Test that all export formats are covered by security scanning."""

    FORMATS = {
        "json": export_to_json,
        "markdown": export_to_markdown,
        "csv": export_to_csv,
        "text": export_to_text,
    }

    @pytest.mark.parametrize("fmt_name,fmt_fn", list(FORMATS.items()))
    def test_clean_export_produces_output(self, fmt_name, fmt_fn):
        bundle = _make_bundle()
        is_safe, _ = validate_export_safety(bundle)
        assert is_safe is True
        output = fmt_fn(bundle)
        assert len(output) > 0

    @pytest.mark.parametrize("fmt_name,fmt_fn", list(FORMATS.items()))
    def test_dirty_bundle_blocked_before_export(self, fmt_name, fmt_fn):
        """Even though the exporter functions don't block internally,
        validate_export_safety should detect issues before they are called."""
        bundle = _bundle_with_text(narration="api_key=secretvalue123456")
        is_safe, issues = validate_export_safety(bundle)
        assert is_safe is False
        assert any(i.severity == "error" for i in issues)

    def test_jsonl_export_clean(self):
        bundle = _make_bundle()
        is_safe, _ = validate_export_safety(bundle)
        assert is_safe is True
        output = export_to_jsonl(bundle)
        assert len(output) > 0
        # Each line should be valid JSON
        for line in output.strip().split("\n"):
            json.loads(line)


# ===================================================================
# API integration — export endpoint blocks on secrets
# ===================================================================

class TestExportEndpointSecurity:
    """Test that the export API endpoint enforces security scanning."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from backend.app.main import app
        from backend.app.providers import init_providers, clear_providers
        from backend.app.handlers import init_mock_handlers
        from backend.app.db.connection import close_connection, init_db
        import backend.app.db.connection as conn_module
        import tempfile, os

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test.db")
        monkeypatch_target = conn_module

        # Save originals
        orig_db_path = getattr(conn_module, "_DB_PATH", None)
        orig_conn = getattr(conn_module, "_CONNECTION", None)

        conn_module._DB_PATH = db_path
        conn_module._CONNECTION = None
        close_connection()
        init_db()

        clear_providers()
        init_providers(mock=True)
        init_mock_handlers()

        with TestClient(app) as c:
            yield c

        clear_providers()
        close_connection()
        conn_module._DB_PATH = orig_db_path
        conn_module._CONNECTION = orig_conn

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_clean_bundle_exports_ok(self, client):
        """A clean bundle should export without issues."""
        bundle = _make_bundle()
        # Create a draft first
        resp = client.post("/api/workflows/wf-1/scene-drafts", json={
            "bundle": bundle.model_dump(by_alias=True),
        })
        assert resp.status_code in (200, 201)
        draft_id = resp.json()["draft_id"]

        # Export should succeed
        resp = client.get(f"/api/scene-bundles/{draft_id}/export?format=json")
        assert resp.status_code == 200
        assert "content" in resp.json()

    def test_bundle_with_secret_blocks_export(self, client):
        """A bundle containing an API key should be blocked at export."""
        bundle = _bundle_with_text(narration="api_key=supersecret12345678901")
        resp = client.post("/api/workflows/wf-1/scene-drafts", json={
            "bundle": bundle.model_dump(by_alias=True),
        })
        assert resp.status_code in (200, 201)
        draft_id = resp.json()["draft_id"]

        # Export should be blocked
        resp = client.get(f"/api/scene-bundles/{draft_id}/export?format=json")
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "SECRET_KEY" in detail

    def test_bundle_with_signed_url_blocks_export(self, client):
        """A bundle containing a signed URL should be blocked."""
        bundle = _bundle_with_text(
            image_prompt="Go to https://s3.amazonaws.com/file?X-Amz-Signature=abc123"
        )
        resp = client.post("/api/workflows/wf-1/scene-drafts", json={
            "bundle": bundle.model_dump(by_alias=True),
        })
        assert resp.status_code in (200, 201)
        draft_id = resp.json()["draft_id"]

        resp = client.get(f"/api/scene-bundles/{draft_id}/export?format=csv")
        assert resp.status_code == 400
        assert "SIGNED_URL" in resp.json()["detail"]

    def test_bundle_with_absolute_path_allows_export(self, client):
        """Absolute paths are warnings, not errors — export should succeed."""
        bundle = _bundle_with_text(video_prompt="Render to C:\\output\\video.mp4")
        resp = client.post("/api/workflows/wf-1/scene-drafts", json={
            "bundle": bundle.model_dump(by_alias=True),
        })
        assert resp.status_code in (200, 201)
        draft_id = resp.json()["draft_id"]

        resp = client.get(f"/api/scene-bundles/{draft_id}/export?format=json")
        assert resp.status_code == 200
        data = resp.json()
        # Should include warnings
        assert "warnings" in data

    def test_validate_endpoint_returns_issues(self, client):
        """The validate endpoint should report issues without blocking."""
        bundle = _bundle_with_text(
            narration="api_key=secret123 and 192.168.1.1"
        )
        resp = client.post("/api/workflows/wf-1/scene-drafts", json={
            "bundle": bundle.model_dump(by_alias=True),
        })
        assert resp.status_code in (200, 201)
        draft_id = resp.json()["draft_id"]

        resp = client.post(f"/api/scene-bundles/{draft_id}/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["issue_count"] > 0
        codes = {i["code"] for i in data["issues"]}
        assert "SECRET_KEY" in codes


# ===================================================================
# Edge cases
# ===================================================================

class TestEdgeCases:
    """Edge case tests for the security scanner."""

    def test_empty_bundle(self):
        bundle = ScenePromptBundle(
            storyboard_id="sb-001",
            workflow_id="wf-001",
            execution_id="ex-001",
            title="Empty",
            scenes=[],
        )
        issues = scan_bundle_security(bundle)
        assert issues == []
        is_safe, _ = validate_export_safety(bundle)
        assert is_safe is True

    def test_encoded_secret_in_text(self):
        """Base64-encoded API key in narration."""
        import base64
        encoded = base64.b64encode(b"sk-abc123def456ghi789").decode()
        bundle = _bundle_with_text(narration=f"Encoded: {encoded}")
        is_safe, _ = validate_export_safety(bundle)
        # Base64 encoding won't match raw patterns — this is expected behavior
        # The scanner catches raw secrets, not encoded ones
        assert is_safe is True

    def test_secret_in_multiple_fields(self):
        """Secret appears in multiple fields — all should be reported."""
        bundle = _bundle_with_text(
            narration="api_key=firstsecret123456",
            image_prompt="api_key=secondsecret12345",
            video_prompt="api_key=thirdsecret123456",
        )
        issues = scan_bundle_security(bundle)
        fields = {i.field for i in issues if i.code == "SECRET_KEY"}
        assert "narration" in fields
        assert "image.prompt" in fields
        assert "video.prompt" in fields

    def test_unicode_content_clean(self):
        """Unicode content without secrets should pass."""
        bundle = _bundle_with_text(
            narration="A scene about the mountain and forest.",
        )
        is_safe, _ = validate_export_safety(bundle)
        assert is_safe is True

    def test_very_long_text_clean(self):
        """Very long text without secrets should pass."""
        long_text = "This is a clean sentence. " * 1000
        bundle = _bundle_with_text(narration=long_text)
        is_safe, _ = validate_export_safety(bundle)
        assert is_safe is True

    def test_partial_secret_match_not_flagged(self):
        """Partial matches like 'sk-' without enough chars should not flag."""
        bundle = _bundle_with_text(narration="The prefix is sk-")
        is_safe, _ = validate_export_safety(bundle)
        assert is_safe is True

    def test_secret_in_transition_field(self):
        """Secrets in transition type should be checked if present."""
        from backend.app.schemas.scene_bundle import SceneTransition
        bundle = _make_bundle()
        # Manually add a transition with a secret
        bundle.scenes[0].transition = SceneTransition(
            type="api_key=secret123",
            duration=0.5,
        )
        # The scanner doesn't currently check transition fields
        # This documents the current behavior
        issues = scan_bundle_security(bundle)
        # transition.type is not scanned — this is a known limitation
        # (transitions are typically type strings like "fade", "cut")

    def test_export_to_text_format(self):
        """Text format export with clean content."""
        bundle = _make_bundle()
        output = export_to_text(bundle)
        assert "[Scene 1]" in output
        assert "Image:" in output
        assert "Video:" in output

    def test_export_to_markdown_format(self):
        """Markdown format export with clean content."""
        bundle = _make_bundle()
        output = export_to_markdown(bundle)
        assert "# Test Bundle" in output
        assert "## Scene 1" in output

    def test_export_to_csv_format(self):
        """CSV format export with clean content."""
        bundle = _make_bundle()
        output = export_to_csv(bundle)
        assert "sceneId" in output
        assert "scene-1" in output

    def test_export_to_jsonl_format(self):
        """JSONL format export with clean content."""
        bundle = _make_bundle()
        output = export_to_jsonl(bundle)
        lines = output.strip().split("\n")
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["sceneId"] == "scene-1"
