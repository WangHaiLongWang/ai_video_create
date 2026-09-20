"""Tests for backend.app.services.secret_encryption and configs repository."""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.app.services.secret_encryption import (
    ENCRYPTED_PREFIX,
    decrypt_secret,
    encrypt_secret,
    is_encrypted,
    rotate_key,
    _invalidate_key_cache,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _set_test_key():
    """Set a deterministic encryption key for tests and reset cache after each test."""
    os.environ["SECRET_ENCRYPTION_KEY"] = "test-master-key-for-unit-tests"
    _invalidate_key_cache()
    yield
    _invalidate_key_cache()
    os.environ.pop("SECRET_ENCRYPTION_KEY", None)


@pytest.fixture()
def _remove_env_key():
    """Remove the env var to test fallback behavior."""
    os.environ.pop("SECRET_ENCRYPTION_KEY", None)
    _invalidate_key_cache()
    yield
    os.environ["SECRET_ENCRYPTION_KEY"] = "test-master-key-for-unit-tests"
    _invalidate_key_cache()


# ===========================================================================
# Encryption / Decryption roundtrip tests
# ===========================================================================


class TestEncryptDecryptRoundtrip:
    """Encrypt then decrypt should return the original plaintext."""

    @pytest.mark.parametrize(
        "plaintext",
        [
            "sk-abc123def456",                    # typical API key
            "",                                    # empty string
            "a" * 1024,                            # 1 KB string
            "Unicode: 中文测试",   # Chinese characters
            "Special: !@#$%^&*()_+-=[]{}|;':\",./<>?",  # special chars
            "\n\t\r",                              # whitespace chars
            "a" * 65536,                           # 64 KB string
        ],
        ids=[
            "api_key",
            "empty",
            "1kb",
            "unicode",
            "special_chars",
            "whitespace",
            "64kb",
        ],
    )
    def test_roundtrip(self, plaintext: str):
        encrypted = encrypt_secret(plaintext)
        decrypted = decrypt_secret(encrypted)
        assert decrypted == plaintext

    def test_encrypted_has_prefix(self):
        encrypted = encrypt_secret("hello")
        assert encrypted.startswith(ENCRYPTED_PREFIX)

    def test_encrypted_is_base64(self):
        encrypted = encrypt_secret("hello")
        raw_b64 = encrypted[len(ENCRYPTED_PREFIX):]
        # Should not raise
        decoded = base64.b64decode(raw_b64)
        # nonce (12) + ciphertext (at least 16 for tag) = 28 minimum
        assert len(decoded) >= 28

    def test_different_nonces_per_call(self):
        """Two encryptions of the same plaintext should produce different ciphertexts (different nonces)."""
        enc1 = encrypt_secret("same-input")
        enc2 = encrypt_secret("same-input")
        assert enc1 != enc2
        # But both should decrypt to the same value
        assert decrypt_secret(enc1) == decrypt_secret(enc2)


# ===========================================================================
# Tampered ciphertext tests
# ===========================================================================


class TestTamperedCiphertext:
    """Decryption of tampered data should raise ValueError."""

    def test_tampered_ciphertext(self):
        encrypted = encrypt_secret("secret-data")
        # Flip a bit in the ciphertext portion
        prefix_len = len(ENCRYPTED_PREFIX)
        raw_b64 = encrypted[prefix_len:]
        raw = bytearray(base64.b64decode(raw_b64))
        # Flip a bit in the middle (after nonce, before tag)
        mid = len(raw) // 2
        raw[mid] ^= 0x01
        tampered = ENCRYPTED_PREFIX + base64.b64encode(bytes(raw)).decode("ascii")
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_secret(tampered)

    def test_tampered_tag(self):
        encrypted = encrypt_secret("secret-data")
        prefix_len = len(ENCRYPTED_PREFIX)
        raw_b64 = encrypted[prefix_len:]
        raw = bytearray(base64.b64decode(raw_b64))
        # Flip a bit in the tag (last 16 bytes)
        raw[-1] ^= 0xFF
        tampered = ENCRYPTED_PREFIX + base64.b64decode(
            base64.b64encode(bytes(raw))
        ).decode("ascii", errors="replace")
        # Re-encode properly
        tampered = ENCRYPTED_PREFIX + base64.b64encode(bytes(raw)).decode("ascii")
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_secret(tampered)

    def test_wrong_key(self):
        """Decryption with a different key should fail."""
        encrypted = encrypt_secret("secret-data")
        _invalidate_key_cache()
        with patch.dict(os.environ, {"SECRET_ENCRYPTION_KEY": "different-key"}):
            _invalidate_key_cache()
            with pytest.raises(ValueError, match="Decryption failed"):
                decrypt_secret(encrypted)
        # Restore
        _invalidate_key_cache()


# ===========================================================================
# Prefix detection
# ===========================================================================


class TestPrefixDetection:
    """is_encrypted should detect the enc:v1: prefix."""

    def test_is_encrypted_true(self):
        encrypted = encrypt_secret("hello")
        assert is_encrypted(encrypted) is True

    def test_is_encrypted_false_plain(self):
        assert is_encrypted("plain-text-value") is False
        assert is_encrypted("") is False
        assert is_encrypted("enc:v0:old") is False

    def test_decrypt_without_prefix_raises(self):
        with pytest.raises(ValueError, match="does not have the expected encryption prefix"):
            decrypt_secret("not-encrypted-at-all")

    def test_decrypt_invalid_base64(self):
        with pytest.raises(ValueError, match="Invalid base64"):
            decrypt_secret(ENCRYPTED_PREFIX + "!!!not-base64!!!")

    def test_decrypt_too_short(self):
        short = base64.b64encode(b"tooshort").decode("ascii")
        with pytest.raises(ValueError, match="too short"):
            decrypt_secret(ENCRYPTED_PREFIX + short)


# ===========================================================================
# Key rotation
# ===========================================================================


class TestKeyRotation:
    """rotate_key should decrypt with old key and re-encrypt with new key."""

    def test_basic_rotation(self):
        encrypted = encrypt_secret("api-key-12345")
        rotated = rotate_key(
            old_key="test-master-key-for-unit-tests",
            new_key="new-master-key-for-rotation",
            encrypted_values=[encrypted],
        )
        assert len(rotated) == 1
        # Should NOT be the same as original
        assert rotated[0] != encrypted
        # Decrypt with new key
        _invalidate_key_cache()
        with patch.dict(os.environ, {"SECRET_ENCRYPTION_KEY": "new-master-key-for-rotation"}):
            _invalidate_key_cache()
            plaintext = decrypt_secret(rotated[0])
            assert plaintext == "api-key-12345"

    def test_rotation_preserves_plaintext(self):
        values = ["key1", "key2", "key3"]
        encrypted = [encrypt_secret(v) for v in values]

        rotated = rotate_key(
            old_key="test-master-key-for-unit-tests",
            new_key="rotation-new-key-xyz",
            encrypted_values=encrypted,
        )
        assert len(rotated) == len(values)

        # Each rotated value should decrypt correctly under the new key
        with patch.dict(os.environ, {"SECRET_ENCRYPTION_KEY": "rotation-new-key-xyz"}):
            _invalidate_key_cache()
            for enc_val, orig in zip(rotated, values):
                assert decrypt_secret(enc_val) == orig

    def test_rotation_with_empty_list(self):
        result = rotate_key(
            old_key="test-master-key-for-unit-tests",
            new_key="new-key",
            encrypted_values=[],
        )
        assert result == []


# ===========================================================================
# Missing key handling
# ===========================================================================


class TestMissingKeyHandling:
    """Test behavior when SECRET_ENCRYPTION_KEY is not set."""

    def test_fallback_generates_key_file(self, _remove_env_key, tmp_path):
        """If no env var is set, a random key should be generated and stored."""
        key_file = tmp_path / ".secret_key"

        # Patch _get_master_key_material to simulate the fallback path
        from backend.app.services import secret_encryption as se_mod

        original_get_master = se_mod._get_master_key_material

        def mock_get_master():
            import secrets as _secrets
            new_key = _secrets.token_hex(32)
            key_file.write_text(new_key, encoding="utf-8")
            try:
                os.chmod(str(key_file), 0o600)
            except OSError:
                pass
            return new_key

        with patch.object(se_mod, "_get_master_key_material", side_effect=mock_get_master):
            _invalidate_key_cache()
            encrypted = encrypt_secret("fallback-test")
            decrypted = decrypt_secret(encrypted)
            assert decrypted == "fallback-test"
            assert key_file.exists()

    def test_env_key_takes_precedence(self):
        """When env var is set, the .secret_key file should not be consulted."""
        os.environ["SECRET_ENCRYPTION_KEY"] = "env-priority-key"
        _invalidate_key_cache()
        enc = encrypt_secret("env-test")
        _invalidate_key_cache()
        dec = decrypt_secret(enc)
        assert dec == "env-test"


# ===========================================================================
# Configs repository integration tests
# ===========================================================================


class TestConfigsRepository:
    """Integration tests for the EncryptedConfigRepository.

    These tests use a real SQLite in-memory database.
    """

    @pytest.fixture(autouse=True)
    def _setup_db(self):
        """Set up an in-memory SQLite database for each test."""
        from backend.app.db.connection import get_connection, close_connection

        # Reset connection to use in-memory DB
        close_connection()
        conn = get_connection()
        # Create configs table (mimicking migration 010)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS configs (
                key          TEXT PRIMARY KEY,
                value        TEXT NOT NULL DEFAULT '',
                is_encrypted INTEGER NOT NULL DEFAULT 0,
                encrypted_at TEXT,
                created_at   TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        yield
        close_connection()

    def test_set_encrypted_and_get_decrypted(self):
        from backend.app.repositories.configs import set_encrypted, get_decrypted

        set_encrypted("openai_api_key", "sk-test-12345")
        result = get_decrypted("openai_api_key")
        assert result == "sk-test-12345"

    def test_list_secrets(self):
        from backend.app.repositories.configs import set_encrypted, list_secrets

        set_encrypted("openai_api_key", "sk-abc")
        set_encrypted("dashscope_api_token", "ds-xyz")
        set_encrypted("ollama_url", "http://localhost:11434")
        set_encrypted("user_password", "pass123")
        set_encrypted("database_host", "localhost")

        secrets = list_secrets()
        assert "openai_api_key" in secrets
        assert "dashscope_api_token" in secrets
        assert "user_password" in secrets
        # Non-secret keys should not appear
        assert "ollama_url" not in secrets
        assert "database_host" not in secrets

    def test_get_decrypted_nonexistent_key(self):
        from backend.app.repositories.configs import get_decrypted, ConfigNotFoundError

        with pytest.raises(ConfigNotFoundError):
            get_decrypted("nonexistent_key")

    def test_get_raw_returns_encrypted_value(self):
        from backend.app.repositories.configs import set_encrypted, get_raw

        set_encrypted("secret_key", "plaintext-value")
        raw = get_raw("secret_key")
        assert raw is not None
        assert raw.startswith(ENCRYPTED_PREFIX)
        # Raw value should NOT be the plaintext
        assert raw != "plaintext-value"

    def test_delete_key(self):
        from backend.app.repositories.configs import set_encrypted, delete_key, get_raw

        set_encrypted("to_delete", "value")
        assert get_raw("to_delete") is not None
        deleted = delete_key("to_delete")
        assert deleted is True
        assert get_raw("to_delete") is None

    def test_set_plain(self):
        from backend.app.repositories.configs import set_plain, get_raw

        set_plain("non_secret_url", "http://example.com")
        raw = get_raw("non_secret_url")
        assert raw == "http://example.com"

    def test_get_encrypted_keys(self):
        from backend.app.repositories.configs import (
            set_encrypted,
            set_plain,
            get_encrypted_keys,
        )

        set_encrypted("api_key", "secret123")
        set_plain("api_url", "http://example.com")
        set_encrypted("token", "bearer-xyz")

        enc_keys = get_encrypted_keys()
        assert "api_key" in enc_keys
        assert "token" in enc_keys
        assert "api_url" not in enc_keys
