"""Tests for SSRF protection — URL validation for private/loopback addresses."""

from __future__ import annotations

import pytest

from backend.app.middleware.ssrf import validate_url, UrlValidator, _is_private_ip


# ---------------------------------------------------------------------------
# _is_private_ip
# ---------------------------------------------------------------------------

class TestIsPrivateIp:
    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",
            "127.0.0.2",
            "10.0.0.1",
            "10.255.255.255",
            "172.16.0.1",
            "172.31.255.255",
            "192.168.0.1",
            "192.168.255.255",
            "169.254.1.1",
            "::1",
            "fc00::1",
            "fe80::1",
        ],
    )
    def test_blocked_ranges(self, ip):
        assert _is_private_ip(ip) is True

    @pytest.mark.parametrize(
        "ip",
        [
            "8.8.8.8",
            "1.1.1.1",
            "203.0.113.5",
            "93.184.216.34",
            "2001:4860:4860::8888",
        ],
    )
    def test_public_ranges(self, ip):
        assert _is_private_ip(ip) is False

    def test_invalid_ip(self):
        assert _is_private_ip("not-an-ip") is False


# ---------------------------------------------------------------------------
# validate_url
# ---------------------------------------------------------------------------

class TestValidateUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1:8080/api",
            "http://10.0.0.1:3000/secret",
            "http://172.16.0.1/internal",
            "http://192.168.1.1/admin",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/loopback",
            "http://[fc00::1]/ ula",
            "http://[fe80::1]/link",
        ],
    )
    def test_blocks_private(self, url):
        assert validate_url(url) is False

    @pytest.mark.parametrize(
        "url",
        [
            "https://api.example.com/v1/data",
            "https://api.openai.com/v1/chat",
            "https://fonts.googleapis.com/css",
        ],
    )
    def test_allows_public(self, url):
        assert validate_url(url) is True

    def test_empty_url(self):
        assert validate_url("") is False

    def test_no_hostname(self):
        assert validate_url("not-a-url") is False


# ---------------------------------------------------------------------------
# UrlValidator
# ---------------------------------------------------------------------------

class TestUrlValidator:
    def test_call(self):
        v = UrlValidator()
        assert v("https://example.com") is True
        assert v("http://127.0.0.1") is False

    def test_assert_safe_raises(self):
        v = UrlValidator()
        with pytest.raises(ValueError, match="Blocked SSRF"):
            v.assert_safe("http://10.0.0.1")

    def test_assert_safe_passes(self):
        v = UrlValidator()
        v.assert_safe("https://example.com")  # should not raise
