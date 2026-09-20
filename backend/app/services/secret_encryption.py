"""AES-256-GCM encryption for secrets at rest.

Provides encrypt/decrypt/rotate functions for protecting API keys and
provider credentials stored in the database.

Key derivation:
- Uses PBKDF2 with 600,000 iterations of SHA-256 to derive a 256-bit key.
- Master key is read from the ``SECRET_ENCRYPTION_KEY`` environment variable.
- If the env var is absent a random key is generated on first use and stored
  in a ``.secret_key`` file next to the project root (with a warning).

Encrypted values use the prefix ``enc:v1:`` followed by a base64-encoded
concatenation of: 12-byte nonce || ciphertext || 16-byte GCM tag.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

# PBKDF2 parameters
_PBKDF2_ITERATIONS = 600_000
_SALT = b"ai_video_create_secret_encryption_v1"  # fixed application-level salt
_KEY_LENGTH = 32  # 256 bits
_NONCE_LENGTH = 12  # 96 bits for GCM

# Encrypted value prefix
ENCRYPTED_PREFIX = "enc:v1:"

_key_cache: bytes | None = None


def _get_master_key_material() -> str:
    """Return the raw master key string from env or fallback file."""
    key = os.environ.get("SECRET_ENCRYPTION_KEY")
    if key:
        return key

    # Fallback: generate and persist a random key
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    key_file = project_root / ".secret_key"

    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()

    # Generate a new random key
    new_key = secrets.token_hex(32)
    try:
        key_file.write_text(new_key, encoding="utf-8")
        # Restrict file permissions on Unix
        try:
            os.chmod(str(key_file), 0o600)
        except OSError:
            pass  # Windows does not support chmod
        logger.warning(
            "No SECRET_ENCRYPTION_KEY env var set. Generated a random key "
            "and stored it in %s. For production, set SECRET_ENCRYPTION_KEY "
            "as an environment variable.",
            key_file,
        )
    except OSError as exc:
        logger.error("Failed to write .secret_key file: %s", exc)
        raise RuntimeError(
            "Cannot create .secret_key fallback file and SECRET_ENCRYPTION_KEY "
            "is not set. Cannot encrypt secrets."
        ) from exc

    return new_key


def _derive_key(master_key_material: str) -> bytes:
    """Derive a 256-bit AES key from the master key material using PBKDF2."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        master_key_material.encode("utf-8"),
        _SALT,
        _PBKDF2_ITERATIONS,
        dklen=_KEY_LENGTH,
    )


def _get_aes_key() -> bytes:
    """Return the derived AES key (cached after first derivation)."""
    global _key_cache
    if _key_cache is None:
        _key_cache = _derive_key(_get_master_key_material())
    return _key_cache


def _invalidate_key_cache() -> None:
    """Clear the cached derived key (used after key rotation)."""
    global _key_cache
    _key_cache = None


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext string using AES-256-GCM.

    Returns a string with prefix ``enc:v1:`` followed by base64-encoded
    ``nonce || ciphertext || tag``.
    """
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(_NONCE_LENGTH)
    # Associated data is empty; the nonce provides uniqueness
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # ciphertext from AESGCM.encrypt already includes the tag (last 16 bytes)
    raw = nonce + ciphertext
    encoded = base64.b64encode(raw).decode("ascii")
    return ENCRYPTED_PREFIX + encoded


def decrypt_secret(encrypted: str) -> str:
    """Decrypt a value produced by :func:`encrypt_secret`.

    Raises ``ValueError`` if the input is not a valid encrypted value or
    decryption fails (e.g. wrong key or tampered data).
    """
    if not encrypted.startswith(ENCRYPTED_PREFIX):
        raise ValueError(
            f"Value does not have the expected encryption prefix '{ENCRYPTED_PREFIX}'"
        )

    raw_b64 = encrypted[len(ENCRYPTED_PREFIX):]
    try:
        raw = base64.b64decode(raw_b64)
    except Exception as exc:
        raise ValueError("Invalid base64 in encrypted value") from exc

    if len(raw) < _NONCE_LENGTH + 16:  # nonce + minimum ciphertext + tag
        raise ValueError("Encrypted value is too short to be valid")

    nonce = raw[:_NONCE_LENGTH]
    ciphertext_with_tag = raw[_NONCE_LENGTH:]

    key = _get_aes_key()
    aesgcm = AESGCM(key)
    try:
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    except Exception as exc:
        raise ValueError(
            "Decryption failed — wrong key or tampered ciphertext"
        ) from exc

    return plaintext_bytes.decode("utf-8")


def is_encrypted(value: str) -> bool:
    """Return True if *value* starts with the encryption prefix."""
    return value.startswith(ENCRYPTED_PREFIX)


def rotate_key(
    old_key: str,
    new_key: str,
    encrypted_values: list[str],
) -> list[str]:
    """Re-encrypt a list of encrypted values with a new master key.

    Parameters
    ----------
    old_key:
        The previous master key material (raw string, same as what was used
        to derive the original AES key).
    new_key:
        The new master key material.
    encrypted_values:
        List of encrypted strings (``enc:v1:...``) to re-encrypt.

    Returns
    -------
    list[str]
        New list of encrypted strings under *new_key*.
    """
    # Temporarily override the key cache to decrypt with the old key
    global _key_cache

    old_derived = _derive_key(old_key)
    new_derived = _derive_key(new_key)

    results: list[str] = []
    for enc_val in encrypted_values:
        # Decrypt with old key
        _key_cache = old_derived
        plaintext = decrypt_secret(enc_val)

        # Encrypt with new key
        _key_cache = new_derived
        results.append(encrypt_secret(plaintext))

    # Restore cache with the new key
    _key_cache = new_derived
    return results
