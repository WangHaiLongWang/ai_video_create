"""Module Security Validator -- enforces size/depth/secret/SSRF limits on module definitions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.app.schemas.module_definition import ModuleDefinition

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CONFIG_SIZE_BYTES = 64 * 1024  # 64 KB
MAX_JSON_DEPTH = 5
MAX_PORTS = 20
MAX_FIELDS = 50
MAX_LABEL_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 500

SECRET_KEYWORDS = re.compile(r"(key|secret|token|password)", re.IGNORECASE)
PORT_ID_RE = re.compile(r"^[a-zA-Z0-9_]+$")
EXECUTION_KEYWORDS = re.compile(r"\b(eval|exec|import|require)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Violation dataclass
# ---------------------------------------------------------------------------


@dataclass
class SecurityViolation:
    """A single security violation found during validation."""

    field: str
    rule: str
    message: str
    severity: str  # "error" or "warning"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_depth(obj: Any, current: int = 0) -> int:
    """Return the maximum nesting depth of a JSON-like object."""
    if isinstance(obj, dict):
        if not obj:
            return current
        return max(_json_depth(v, current + 1) for v in obj.values())
    if isinstance(obj, list):
        if not obj:
            return current
        return max(_json_depth(v, current + 1) for v in obj)
    return current


def _count_properties(schema: dict) -> int:
    """Count total properties recursively in a JSON Schema."""
    count = 0
    props = schema.get("properties", {})
    count += len(props)
    for prop_schema in props.values():
        if isinstance(prop_schema, dict):
            count += _count_properties(prop_schema)
    # Also count items.properties for array schemas (only if "items" key exists)
    if "items" in schema and isinstance(schema["items"], dict):
        count += _count_properties(schema["items"])
    # allOf / oneOf / anyOf
    for combo_key in ("allOf", "oneOf", "anyOf"):
        for sub in schema.get(combo_key, []):
            if isinstance(sub, dict):
                count += _count_properties(sub)
    return count


def _find_secret_keys(schema: dict, path: str = "") -> list[str]:
    """Find property keys that look like secrets."""
    findings: list[str] = []
    props = schema.get("properties", {})
    for key, prop_schema in props.items():
        current_path = f"{path}.{key}" if path else key
        if SECRET_KEYWORDS.search(key):
            findings.append(current_path)
        if isinstance(prop_schema, dict):
            findings.extend(_find_secret_keys(prop_schema, current_path))
    if "items" in schema and isinstance(schema["items"], dict):
        findings.extend(_find_secret_keys(schema["items"], f"{path}[]"))
    return findings


def _find_execution_keywords(schema: dict, path: str = "") -> list[str]:
    """Find fields whose titles contain execution-related keywords."""
    findings: list[str] = []
    props = schema.get("properties", {})
    for key, prop_schema in props.items():
        current_path = f"{path}.{key}" if path else key
        if isinstance(prop_schema, dict):
            title = prop_schema.get("title", "")
            if title and EXECUTION_KEYWORDS.search(title):
                findings.append(current_path)
            findings.extend(_find_execution_keywords(prop_schema, current_path))
    if "items" in schema and isinstance(schema["items"], dict):
        findings.extend(_find_execution_keywords(schema["items"], f"{path}[]"))
    return findings


# ---------------------------------------------------------------------------
# Main validator
# ---------------------------------------------------------------------------


def validate_module_security(
    definition: ModuleDefinition,
) -> list[SecurityViolation]:
    """Check a module definition for security issues.

    Returns a list of :class:`SecurityViolation` items.  Items with
    ``severity == "error"`` must block publishing; ``"warning"`` items are
    informational only.
    """
    violations: list[SecurityViolation] = []

    schema_json = json.dumps(definition.config_schema, ensure_ascii=False)

    # 1. MAX_CONFIG_SIZE
    size_bytes = len(schema_json.encode("utf-8"))
    if size_bytes > MAX_CONFIG_SIZE_BYTES:
        violations.append(
            SecurityViolation(
                field="configSchema",
                rule="MAX_CONFIG_SIZE",
                message=f"configSchema is {size_bytes} bytes, exceeds {MAX_CONFIG_SIZE_BYTES} byte limit",
                severity="error",
            )
        )

    # 2. MAX_JSON_DEPTH
    depth = _json_depth(definition.config_schema)
    if depth > MAX_JSON_DEPTH:
        violations.append(
            SecurityViolation(
                field="configSchema",
                rule="MAX_JSON_DEPTH",
                message=f"configSchema nesting depth is {depth}, exceeds maximum of {MAX_JSON_DEPTH}",
                severity="error",
            )
        )

    # 3. MAX_PORTS
    input_ports = definition.ports.get("inputs", [])
    output_ports = definition.ports.get("outputs", [])
    total_ports = len(input_ports) + len(output_ports)
    if total_ports > MAX_PORTS:
        violations.append(
            SecurityViolation(
                field="ports",
                rule="MAX_PORTS",
                message=f"Total ports ({total_ports}) exceeds maximum of {MAX_PORTS}",
                severity="error",
            )
        )

    # 4. MAX_FIELDS
    field_count = _count_properties(definition.config_schema)
    if field_count > MAX_FIELDS:
        violations.append(
            SecurityViolation(
                field="configSchema",
                rule="MAX_FIELDS",
                message=f"configSchema has {field_count} properties, exceeds maximum of {MAX_FIELDS}",
                severity="error",
            )
        )

    # 5. SECRET_REJECTION
    secret_keys = _find_secret_keys(definition.config_schema)
    for key_path in secret_keys:
        violations.append(
            SecurityViolation(
                field=f"configSchema.{key_path}",
                rule="SECRET_REJECTION",
                message=f"Property key '{key_path}' contains a secret-related keyword",
                severity="error",
            )
        )

    # 6. PORT_ID_FORMAT
    for port_list, port_type in [(input_ports, "inputs"), (output_ports, "outputs")]:
        for port in port_list:
            port_id = port.get("id", "")
            if not PORT_ID_RE.match(port_id):
                violations.append(
                    SecurityViolation(
                        field=f"ports.{port_type}[{port.get('id', '?')}]",
                        rule="PORT_ID_FORMAT",
                        message=f"Port ID '{port_id}' must be alphanumeric/underscore only",
                        severity="error",
                    )
                )

    # 7. LABEL_LENGTH
    if len(definition.label) > MAX_LABEL_LENGTH:
        violations.append(
            SecurityViolation(
                field="label",
                rule="LABEL_LENGTH",
                message=f"Label length ({len(definition.label)}) exceeds {MAX_LABEL_LENGTH} characters",
                severity="warning",
            )
        )

    # 8. DESCRIPTION_LENGTH
    if len(definition.description) > MAX_DESCRIPTION_LENGTH:
        violations.append(
            SecurityViolation(
                field="description",
                rule="DESCRIPTION_LENGTH",
                message=f"Description length ({len(definition.description)}) exceeds {MAX_DESCRIPTION_LENGTH} characters",
                severity="warning",
            )
        )

    # 9. NO_EXECUTION_IN_SCHEMA
    exec_fields = _find_execution_keywords(definition.config_schema)
    for field_path in exec_fields:
        violations.append(
            SecurityViolation(
                field=f"configSchema.{field_path}",
                rule="NO_EXECUTION_IN_SCHEMA",
                message=f"Property '{field_path}' title contains suspicious keyword",
                severity="error",
            )
        )

    # 10. PROVIDER_LOCKDOWN
    pp = definition.provider_policy
    if pp.locked and not pp.allowed:
        violations.append(
            SecurityViolation(
                field="providerPolicy.allowed",
                rule="PROVIDER_LOCKDOWN",
                message="Locked provider policy must have a non-empty allowed list",
                severity="error",
            )
        )

    return violations
