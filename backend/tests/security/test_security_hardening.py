"""安全加固测试 — SSRF 防护、路径安全、密钥脱敏、安全头。"""

from __future__ import annotations

import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.providers import init_providers, clear_providers
from backend.app.handlers import init_mock_handlers
from backend.app.db.connection import close_connection, init_db
import backend.app.db.connection as conn_module

from backend.app.security.url_policy import (
    URLPolicy, SSRFError, is_safe_url, _is_private_ip,
)
from backend.app.security.path_safety import (
    PathSafety, PathTraversalError, validate_asset_path, _sanitize_filename,
)
from backend.app.security.secrets_mask import (
    SecretsMask, mask_secrets, _mask_value,
)
from backend.app.services.asset_manager import AssetManager


# ============================================================
# SSRF 防护测试
# ============================================================

class TestSSRFProtection:
    """SSRF 防护测试。"""

    def test_blocks_loopback_ip(self):
        """阻止 loopback IP (127.0.0.1)。"""
        policy = URLPolicy()
        with pytest.raises(SSRFError, match="私有 IP"):
            policy.check_url("http://127.0.0.1/admin")

    def test_blocks_loopback_ip_variants(self):
        """阻止 loopback IP 变体。"""
        policy = URLPolicy()
        with pytest.raises(SSRFError, match="私有 IP"):
            policy.check_url("http://127.0.0.2/secret")

    def test_blocks_private_class_a(self):
        """阻止 Class A 私有网络 (10.x.x.x)。"""
        policy = URLPolicy()
        with pytest.raises(SSRFError, match="私有 IP"):
            policy.check_url("http://10.0.0.1/internal")

    def test_blocks_private_class_b(self):
        """阻止 Class B 私有网络 (172.16.x.x)。"""
        policy = URLPolicy()
        with pytest.raises(SSRFError, match="私有 IP"):
            policy.check_url("http://172.16.0.1/internal")

    def test_blocks_private_class_c(self):
        """阻止 Class C 私有网络 (192.168.x.x)。"""
        policy = URLPolicy()
        with pytest.raises(SSRFError, match="私有 IP"):
            policy.check_url("http://192.168.1.1/router")

    def test_blocks_link_local(self):
        """阻止 link-local 地址 (169.254.x.x)。"""
        policy = URLPolicy()
        with pytest.raises(SSRFError, match="私有 IP"):
            policy.check_url("http://169.254.169.254/metadata")

    def test_blocks_zero_network(self):
        """阻止 0.0.0.0 网络。"""
        policy = URLPolicy()
        with pytest.raises(SSRFError, match="私有 IP"):
            policy.check_url("http://0.0.0.0/secret")

    def test_blocks_non_http_schemes(self):
        """阻止非 HTTP/HTTPS 协议。"""
        policy = URLPolicy()
        with pytest.raises(SSRFError, match="不支持的协议"):
            policy.check_url("file:///etc/passwd")
        with pytest.raises(SSRFError, match="不支持的协议"):
            policy.check_url("ftp://example.com/file")
        with pytest.raises(SSRFError, match="不支持的协议"):
            policy.check_url("javascript:alert(1)")
        with pytest.raises(SSRFError, match="不支持的协议"):
            policy.check_url("data:text/html,<h1>hi</h1>")

    def test_blocks_missing_hostname(self):
        """阻止缺少主机名的 URL。"""
        policy = URLPolicy()
        with pytest.raises(SSRFError, match="缺少主机名"):
            policy.check_url("http://")

    def test_is_safe_url_returns_false_for_private(self):
        """is_safe_url 对私有 IP 返回 False。"""
        assert is_safe_url("http://10.0.0.1/api") is False
        assert is_safe_url("http://127.0.0.1:8080/") is False
        assert is_safe_url("http://192.168.1.1/") is False

    def test_is_safe_url_returns_false_for_bad_scheme(self):
        """is_safe_url 对不安全协议返回 False。"""
        assert is_safe_url("file:///etc/passwd") is False
        assert is_safe_url("ftp://example.com") is False

    def test_is_safe_url_returns_true_for_safe_url(self):
        """is_safe_url 对安全 URL 返回 True（仅 scheme 检查）。"""
        assert is_safe_url("https://api.example.com/data") is True

    def test_ipv6_loopback_blocked(self):
        """阻止 IPv6 loopback。"""
        assert _is_private_ip("::1") is True

    def test_ipv6_link_local_blocked(self):
        """阻止 IPv6 link-local。"""
        assert _is_private_ip("fe80::1") is True

    def test_ipv6_unique_local_blocked(self):
        """阻止 IPv6 unique local。"""
        assert _is_private_ip("fc00::1") is True


# ============================================================
# 路径安全测试
# ============================================================

class TestPathSafety:
    """路径安全测试。"""

    def test_blocks_dot_dot_sequence(self):
        """阻止 .. 路径序列。"""
        with pytest.raises(PathTraversalError, match="危险模式"):
            validate_asset_path("../../etc/passwd", "/tmp/assets")

    def test_blocks_encoded_dot_dot(self):
        """阻止 URL 编码的 .. 序列。"""
        with pytest.raises(PathTraversalError, match="危险模式"):
            validate_asset_path("%2e%2e/etc/passwd", "/tmp/assets")

    def test_blocks_absolute_path(self):
        """阻止绝对路径。"""
        safety = PathSafety(root_dirs=["/tmp/assets"])
        with pytest.raises(PathTraversalError, match="根目录之外"):
            safety.validate_path("/etc/passwd")

    def test_blocks_path_outside_root(self):
        """阻止访问根目录之外的路径。"""
        safety = PathSafety(root_dirs=["/tmp/assets"])
        with pytest.raises(PathTraversalError):
            safety.validate_path("../../../etc/passwd")

    def test_allows_valid_relative_path(self):
        """允许合法的相对路径。"""
        safety = PathSafety(root_dirs=["/tmp/assets"])
        result = safety.validate_path("images/photo.png")
        assert result is not None

    def test_sanitize_filename_removes_dangerous_chars(self):
        """清理文件名中的危险字符。"""
        assert _sanitize_filename("../../etc/passwd") == "etc_passwd"
        assert _sanitize_filename("file name.txt") == "file_name_txt"
        assert _sanitize_filename("../../../secret") == "secret"

    def test_sanitize_filename_prevents_hidden_files(self):
        """清理文件名防止隐藏文件。"""
        assert _sanitize_filename(".hidden") == "hidden"
        assert _sanitize_filename("...hidden") == "hidden"

    def test_sanitize_filename_handles_empty(self):
        """处理空文件名。"""
        assert _sanitize_filename("") == "unnamed"
        assert _sanitize_filename("///") == "unnamed"

    def test_sanitize_filename_truncates_long_names(self):
        """截断过长文件名。"""
        long_name = "a" * 300 + ".txt"
        result = _sanitize_filename(long_name)
        assert len(result) <= 255

    def test_asset_manager_blocks_traversal_read(self):
        """AssetManager 阻止路径遍历读取。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = AssetManager(tmpdir)
            with pytest.raises(PathTraversalError):
                manager.read_asset("../../etc/passwd")

    def test_asset_manager_blocks_traversal_delete(self):
        """AssetManager 阻止路径遍历删除。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = AssetManager(tmpdir)
            with pytest.raises(PathTraversalError):
                manager.delete_asset("../../important_file")

    def test_asset_manager_blocks_traversal_info(self):
        """AssetManager 阻止路径遍历获取信息。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = AssetManager(tmpdir)
            with pytest.raises(PathTraversalError):
                manager.get_asset_info("../../etc/passwd")

    def test_asset_manager_allows_valid_path(self):
        """AssetManager 允许合法路径操作。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = AssetManager(tmpdir)
            path = manager.save_asset(b"test data", category="images")
            assert manager.asset_exists(path)
            data = manager.read_asset(path)
            assert data == b"test data"

    def test_is_safe_relative_blocks_traversal(self):
        """is_safe_relative 阻止路径遍历。"""
        safety = PathSafety()
        assert safety.is_safe_relative("images/photo.png", "/tmp/assets") is True
        assert safety.is_safe_relative("../../etc/passwd", "/tmp/assets") is False

    def test_tilde_expansion_blocked(self):
        """阻止 ~ 家目录展开。"""
        with pytest.raises(PathTraversalError, match="危险模式"):
            validate_asset_path("~/secret", "/tmp/assets")


# ============================================================
# 密钥脱敏测试
# ============================================================

class TestSecretsMasking:
    """密钥脱敏测试。"""

    def test_masks_openai_api_key(self):
        """脱敏 OpenAI API Key。"""
        text = "Using API key: sk-abc123def456ghi789jkl012mno345pqr678stu901"
        masked = mask_secrets(text)
        assert "sk-abc123def456ghi789jkl012mno345pqr678stu901" not in masked
        assert "sk-" in masked
        assert "***" in masked

    def test_masks_bearer_token(self):
        """脱敏 Bearer Token。"""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        masked = mask_secrets(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in masked
        assert "Bearer " in masked

    def test_masks_api_key_assignment(self):
        """脱敏 api_key=xxx 格式。"""
        text = "api_key=super_secret_key_12345678"
        masked = mask_secrets(text)
        assert "super_secret_key_12345678" not in masked
        assert "api_key=" in masked

    def test_masks_aws_access_key(self):
        """脱敏 AWS Access Key。"""
        text = "AWS key: AKIAIOSFODNN7EXAMPLE"
        masked = mask_secrets(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in masked
        assert "AKIA" in masked

    def test_masks_github_token(self):
        """脱敏 GitHub Token。"""
        text = "token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnop"
        masked = mask_secrets(text)
        assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnop" not in masked

    def test_preserves_normal_strings(self):
        """保留正常字符串不变。"""
        text = "Hello world, this is a normal message with no secrets."
        masked = mask_secrets(text)
        assert masked == text

    def test_preserves_empty_string(self):
        """保留空字符串。"""
        assert mask_secrets("") == ""
        assert mask_secrets(None) is None

    def test_preserves_short_hex(self):
        """保留短的十六进制字符串（不视为密钥）。"""
        text = "Color code: ff00ff"
        masked = mask_secrets(text)
        assert masked == text

    def test_masks_long_hex_token(self):
        """脱敏长十六进制 Token。"""
        text = "Token: abcdef0123456789abcdef0123456789"
        masked = mask_secrets(text)
        assert "abcdef0123456789abcdef0123456789" not in masked

    def test_mask_value_helper(self):
        """测试 _mask_value 辅助函数。"""
        assert _mask_value("short") == "*****"
        assert _mask_value("abcdefgh") == "********"  # 8 chars, 8 <= 4+4, fully masked
        assert _mask_value("abcdefghijklmnop") == "abcd********mnop"

    def test_secrets_mask_class_with_custom_pattern(self):
        """SecretsMask 类支持自定义模式。"""
        import re
        custom = [("MYTOKEN", re.compile(r"MYTOKEN-[A-Z]{6}"))]
        masker = SecretsMask(extra_patterns=custom)
        text = "Code: MYTOKEN-ABCDEF"
        masked = masker.mask(text)
        assert "ABCDEF" not in masked
        # The custom pattern should have masked the token part
        assert masked != text

    def test_masks_multiple_secrets_in_one_string(self):
        """脱敏同一字符串中的多个密钥。"""
        text = (
            "openai_key=sk-realkey1234567890123456 "
            "dashscope=sk-dashscope1234567890123456"
        )
        masked = mask_secrets(text)
        assert "sk-realkey1234567890123456" not in masked
        assert "sk-dashscope1234567890123456" not in masked

    def test_masks_password_assignment(self):
        """脱敏 password=xxx 格式。"""
        text = "password=my_secret_pass_123"
        masked = mask_secrets(text)
        assert "my_secret_pass_123" not in masked
        assert "password=" in masked


# ============================================================
# 安全头测试
# ============================================================

class TestSecurityHeadersInResponse:
    """安全响应头在实际 HTTP 响应中的测试。"""

    def test_security_headers_present(self, client):
        """检查所有安全响应头都存在。"""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert response.headers.get("Content-Security-Policy") in (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
            "default-src 'self'",
        )

    def test_security_headers_on_post(self, client):
        """POST 请求也应返回安全头。"""
        response = client.post("/api/workflows/validate", json={
            "nodes": [], "edges": [],
        })
        # Whether 200 or 422, security headers should be present
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("Content-Security-Policy") in (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
            "default-src 'self'",
        )

    def test_security_headers_on_404(self, client):
        """404 响应也应返回安全头。"""
        response = client.get("/api/nonexistent")
        # 404 still gets middleware headers
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_security_headers_on_error(self, client):
        """错误响应也应返回安全头。"""
        response = client.post("/api/workflows", json={})
        assert response.status_code == 422
        assert response.headers.get("X-Content-Type-Options") == "nosniff"


# ============================================================
# 速率限制和请求大小限制测试
# ============================================================

class TestRateLimitingAndBodySize:
    """速率限制和请求体大小限制测试。"""

    def test_rate_limit_triggers(self):
        """速率限制在超过阈值时触发。"""
        # 创建独立 app 实例避免与其他测试共享计数器
        from fastapi import FastAPI
        from backend.app.middleware import SecurityMiddleware

        test_app = FastAPI()

        @test_app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        # 使用低限制的独立中间件
        test_app.add_middleware(SecurityMiddleware, rate_limit=5)

        with TestClient(test_app) as c:
            for _ in range(5):
                c.get("/test")
            response = c.get("/test")
            assert response.status_code == 429
            assert "请求过于频繁" in response.json()["detail"]

    def test_body_size_limit_on_large_post(self, client):
        """大型 POST 请求被拒绝。"""
        # 发送超过 10MB 的请求体
        large_body = "x" * (10 * 1024 * 1024 + 1)
        response = client.post(
            "/api/workflows/validate",
            content=large_body,
            headers={"Content-Type": "application/json"},
        )
        # Should be 413 (body too large) or 429 (rate limited) — both are security measures
        assert response.status_code in (413, 429)


# ============================================================
# 密钥脱敏过滤器测试
# ============================================================

class TestSecretsMaskingFilter:
    """密钥脱敏日志过滤器测试。"""

    def test_filter_masks_log_message(self):
        """过滤器脱敏日志消息。"""
        import logging
        from backend.app.middleware import SecretsMaskingFilter

        filt = SecretsMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="API key: sk-abc123def456ghi789jkl012mno345pqr678stu901",
            args=None,
            exc_info=None,
        )
        filt.filter(record)
        assert "sk-abc123def456ghi789jkl012mno345pqr678stu901" not in record.msg

    def test_filter_preserves_normal_message(self):
        """过滤器保留正常日志消息。"""
        import logging
        from backend.app.middleware import SecretsMaskingFilter

        filt = SecretsMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Normal log message with no secrets",
            args=None,
            exc_info=None,
        )
        result = filt.filter(record)
        assert result is True
        assert record.msg == "Normal log message with no secrets"

    def test_filter_masks_tuple_args(self):
        """过滤器脱敏元组参数。"""
        import logging
        from backend.app.middleware import SecretsMaskingFilter

        filt = SecretsMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Connecting with key %s to %s",
            args=("sk-abc123def456ghi789jkl012mno345pqr678stu901", "https://api.example.com"),
            exc_info=None,
        )
        filt.filter(record)
        # The first arg should be masked
        masked_key = record.args[0]
        assert "sk-abc123def456ghi789jkl012mno345pqr678stu901" not in masked_key

    def test_filter_masks_string_args_in_tuple(self):
        """过滤器脱敏元组中的字符串参数（含 key=value 格式）。"""
        import logging
        from backend.app.middleware import SecretsMaskingFilter

        filt = SecretsMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Config: %s",
            args=("api_key=super_secret_12345678",),
            exc_info=None,
        )
        filt.filter(record)
        # The string arg should be masked
        assert "super_secret_12345678" not in record.args[0]


# ============================================================
# Symlink 逃逸测试
# ============================================================

class TestSymlinkEscape:
    """符号链接逃逸测试。"""

    def test_detects_symlink_escape(self):
        """检测符号链接逃逸。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "assets"
            root.mkdir()
            outside = Path(tmpdir) / "outside"
            outside.mkdir()
            secret_file = outside / "secret.txt"
            secret_file.write_text("secret content")

            # 创建指向外部的符号链接
            link = root / "escape_link"
            try:
                link.symlink_to(outside)
            except OSError:
                pytest.skip("操作系统不支持符号链接")

            safety = PathSafety(root_dirs=[root])
            with pytest.raises(PathTraversalError, match="符号链接"):
                safety.validate_path("escape_link/secret.txt")
