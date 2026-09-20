"""EncryptedConfigRepository — key-value config store with transparent encryption.

Values stored via :func:`set_encrypted` are encrypted with AES-256-GCM before
being written to the ``configs`` table.  Values retrieved via :func:`get_decrypted`
are transparently decrypted.

Encrypted values are prefixed with ``enc:v1:`` so the repository can detect
whether a value needs decryption without relying solely on the ``is_encrypted``
column.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.app.db.connection import get_connection
from backend.app.services.secret_encryption import (
    ENCRYPTED_PREFIX,
    decrypt_secret,
    encrypt_secret,
    is_encrypted,
)

# Patterns that indicate a key holds a secret value
_SECRET_KEY_PATTERNS = ("key", "token", "secret", "password", "credential")


class ConfigNotFoundError(Exception):
    """Raised when a requested config key does not exist."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_decrypted(key: str) -> str:
    """Return the plaintext value for *key*, decrypting if necessary.

    Raises :class:`ConfigNotFoundError` if the key is not in the table.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT value, is_encrypted FROM configs WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        raise ConfigNotFoundError(f"Config key '{key}' not found")

    value: str = row["value"]

    # Decrypt if the database flag is set or the prefix is detected
    if row["is_encrypted"] or is_encrypted(value):
        value = decrypt_secret(value)

    return value


def set_encrypted(key: str, value: str) -> None:
    """Encrypt *value* and upsert it into the ``configs`` table.

    If *value* is already encrypted (has the ``enc:v1:`` prefix), it is
    stored as-is without double encryption.
    """
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()

    if is_encrypted(value):
        # Already encrypted — store as-is
        stored_value = value
        is_enc = 1
    else:
        stored_value = encrypt_secret(value)
        is_enc = 1

    conn.execute(
        """
        INSERT INTO configs (key, value, is_encrypted, encrypted_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            is_encrypted = excluded.is_encrypted,
            encrypted_at = excluded.encrypted_at,
            updated_at = excluded.updated_at
        """,
        (key, stored_value, is_enc, now, now, now),
    )
    conn.commit()


def set_plain(key: str, value: str) -> None:
    """Store a plaintext value (no encryption).

    Useful for non-sensitive configuration entries.
    """
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO configs (key, value, is_encrypted, created_at, updated_at)
        VALUES (?, ?, 0, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            is_encrypted = 0,
            encrypted_at = NULL,
            updated_at = excluded.updated_at
        """,
        (key, value, now, now),
    )
    conn.commit()


def get_raw(key: str) -> str | None:
    """Return the raw stored value for *key* (no decryption).

    Returns ``None`` if the key does not exist.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT value FROM configs WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else None


def list_secrets() -> list[str]:
    """Return config keys that likely contain secret values.

    Detection is based on common naming conventions: the key contains one of
    ``key``, ``token``, ``secret``, ``password``, or ``credential`` (case-insensitive).
    """
    conn = get_connection()
    rows = conn.execute("SELECT key FROM configs").fetchall()
    secrets: list[str] = []
    for row in rows:
        k = row["key"].lower()
        if any(pat in k for pat in _SECRET_KEY_PATTERNS):
            secrets.append(row["key"])
    return secrets


def list_all_keys() -> list[str]:
    """Return all config keys."""
    conn = get_connection()
    rows = conn.execute("SELECT key FROM configs ORDER BY key").fetchall()
    return [row["key"] for row in rows]


def delete_key(key: str) -> bool:
    """Delete a config key. Returns True if a row was deleted."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM configs WHERE key = ?", (key,))
    conn.commit()
    return cursor.rowcount > 0


def get_encrypted_keys() -> list[str]:
    """Return keys whose values are currently encrypted in the database."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT key FROM configs WHERE is_encrypted = 1"
    ).fetchall()
    return [row["key"] for row in rows]


def re_encrypt_value(key: str, new_encrypted_value: str) -> None:
    """Replace the stored value for *key* with *new_encrypted_value*.

    Used during key rotation.
    """
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        UPDATE configs
        SET value = ?, is_encrypted = 1, encrypted_at = ?, updated_at = ?
        WHERE key = ?
        """,
        (new_encrypted_value, now, now, key),
    )
    conn.commit()
