"""Persistent named provider configurations.

Only non-sensitive metadata is stored in ``provider_configs``. API keys and
other credentials are stored through the encrypted config repository using a
stable ``provider_config.<id>.*`` key namespace.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.app.db.connection import get_connection
from backend.app.repositories.configs import delete_key, get_decrypted, set_encrypted

_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,127}$")
_SECRET_FIELDS = {"api_key", "access_token", "secret", "password"}
_PROVIDER_TYPES = {"mock", "ollama", "openai", "openai_compat", "dashscope", "wan3", "doubao", "comfyui"}
_CAPABILITIES = {"text", "image", "video"}


class ProviderConfigNotFoundError(KeyError):
    pass


class ProviderConfigValidationError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(row) -> dict[str, Any]:
    value = dict(row)
    value["config"] = json.loads(value.pop("config_json") or "{}")
    value["capabilities"] = json.loads(value.pop("capabilities_json") or "{}")
    value["default_capabilities"] = json.loads(value.pop("default_capabilities_json") or "[]")
    value["enabled"] = bool(value["enabled"])
    value["has_credentials"] = any(get_secret(value["id"], f) is not None for f in _SECRET_FIELDS)
    return value


def get_secret(config_id: str, field: str) -> str | None:
    try:
        return get_decrypted(f"provider_config.{config_id}.{field}")
    except Exception:
        return None


def list_provider_configs() -> list[dict[str, Any]]:
    rows = get_connection().execute("SELECT * FROM provider_configs ORDER BY name").fetchall()
    return [_row(r) for r in rows]


def get_provider_config(config_id: str) -> dict[str, Any]:
    row = get_connection().execute("SELECT * FROM provider_configs WHERE id = ?", (config_id,)).fetchone()
    if row is None:
        raise ProviderConfigNotFoundError(config_id)
    return _row(row)


def create_provider_config(*, name: str, provider_type: str, config: dict[str, Any] | None = None,
                           capabilities: dict[str, bool] | None = None,
                           default_capabilities: list[str] | None = None,
                           enabled: bool = True, secrets: dict[str, str] | None = None,
                           config_id: str | None = None) -> dict[str, Any]:
    name = name.strip()
    if not name or len(name) > 160:
        raise ProviderConfigValidationError("name must be 1..160 characters")
    if provider_type not in _PROVIDER_TYPES:
        raise ProviderConfigValidationError("unsupported provider type")
    capabilities = capabilities or {}
    if set(capabilities) - _CAPABILITIES or any(not isinstance(v, bool) for v in capabilities.values()):
        raise ProviderConfigValidationError("capabilities must contain boolean text/image/video values")
    default_capabilities = list(dict.fromkeys(default_capabilities or []))
    if set(default_capabilities) - _CAPABILITIES:
        raise ProviderConfigValidationError("invalid default capability")
    if any(not capabilities.get(capability, False) for capability in default_capabilities):
        raise ProviderConfigValidationError("a default capability must be enabled by the profile")
    cid = (config_id or f"pc_{uuid.uuid4().hex[:16]}").strip()
    if not _ID_RE.match(cid):
        raise ProviderConfigValidationError("invalid config id")
    payload = dict(config or {})
    payload = {k: v for k, v in payload.items() if k not in _SECRET_FIELDS}
    now = _now()
    conn = get_connection()
    try:
        conn.execute("INSERT INTO provider_configs (id,name,provider_type,config_json,capabilities_json,default_capabilities_json,enabled,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (cid, name, provider_type, json.dumps(payload, ensure_ascii=False), json.dumps(capabilities, ensure_ascii=False), json.dumps(default_capabilities, ensure_ascii=False), int(enabled), now, now))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    for field, value in (secrets or {}).items():
        if field in _SECRET_FIELDS and value:
            set_encrypted(f"provider_config.{cid}.{field}", value)
    return get_provider_config(cid)


def update_provider_config(config_id: str, **changes: Any) -> dict[str, Any]:
    current = get_provider_config(config_id)
    fields = {"name", "provider_type", "config", "capabilities", "default_capabilities", "enabled"}
    updates = {k: v for k, v in changes.items() if k in fields and v is not None}
    if "name" in updates and (not str(updates["name"]).strip() or len(str(updates["name"])) > 160):
        raise ProviderConfigValidationError("name must be 1..160 characters")
    if "provider_type" in updates and updates["provider_type"] not in _PROVIDER_TYPES:
        raise ProviderConfigValidationError("unsupported provider type")
    if "config" in updates:
        updates["config"] = {k: v for k, v in dict(updates["config"]).items() if k not in _SECRET_FIELDS}
    if updates:
        now = _now()
        encoded = {"name": current["name"], "provider_type": current["provider_type"], "config_json": json.dumps(current["config"], ensure_ascii=False), "capabilities_json": json.dumps(current["capabilities"], ensure_ascii=False), "default_capabilities_json": json.dumps(current["default_capabilities"], ensure_ascii=False), "enabled": int(current["enabled"])}
        encoded.update({"name": updates.get("name", encoded["name"]), "provider_type": updates.get("provider_type", encoded["provider_type"]), "config_json": json.dumps(updates.get("config", current["config"]), ensure_ascii=False), "capabilities_json": json.dumps(updates.get("capabilities", current["capabilities"]), ensure_ascii=False), "default_capabilities_json": json.dumps(updates.get("default_capabilities", current["default_capabilities"]), ensure_ascii=False), "enabled": int(updates.get("enabled", current["enabled"]))})
        get_connection().execute("UPDATE provider_configs SET name=?,provider_type=?,config_json=?,capabilities_json=?,default_capabilities_json=?,enabled=?,updated_at=? WHERE id=?", (*[encoded[k] for k in ("name","provider_type","config_json","capabilities_json","default_capabilities_json","enabled")], now, config_id))
        get_connection().commit()
    for field, value in (changes.get("secrets") or {}).items():
        if field in _SECRET_FIELDS:
            key = f"provider_config.{config_id}.{field}"
            if value:
                set_encrypted(key, value)
            elif value == "":
                delete_key(key)
    return get_provider_config(config_id)


def delete_provider_config(config_id: str) -> None:
    get_provider_config(config_id)
    conn = get_connection()
    conn.execute("DELETE FROM provider_configs WHERE id = ?", (config_id,))
    conn.commit()
    for field in _SECRET_FIELDS:
        delete_key(f"provider_config.{config_id}.{field}")


def set_default(config_id: str, capability: str) -> dict[str, Any]:
    item = get_provider_config(config_id)
    if capability not in {"text", "image", "video"}:
        raise ProviderConfigValidationError("capability must be text, image or video")
    if not item["enabled"] or not item["capabilities"].get(capability, False):
        raise ProviderConfigValidationError("profile is disabled or does not provide this capability")
    conn = get_connection()
    rows = conn.execute("SELECT id, default_capabilities_json FROM provider_configs").fetchall()
    for row in rows:
        caps = json.loads(row["default_capabilities_json"] or "[]")
        caps = [c for c in caps if c != capability]
        if row["id"] == config_id:
            caps.append(capability)
        conn.execute("UPDATE provider_configs SET default_capabilities_json=?, updated_at=? WHERE id=?", (json.dumps(caps), _now(), row["id"]))
    conn.commit()
    return get_provider_config(config_id)


def get_default_provider_config_id(capability: str) -> str | None:
    """Return the enabled profile selected as default for a capability."""
    if capability not in {"text", "image", "video"}:
        return None
    try:
        rows = get_connection().execute(
            "SELECT id, default_capabilities_json FROM provider_configs WHERE enabled = 1 ORDER BY name"
        ).fetchall()
    except Exception:
        # Unit-level handler tests may intentionally run without DB bootstrap.
        return None
    for row in rows:
        if capability in json.loads(row["default_capabilities_json"] or "[]"):
            return str(row["id"])
    return None
