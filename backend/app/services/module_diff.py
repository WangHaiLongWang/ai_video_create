"""Module Diff — structural diff between two module versions for safe upgrades."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.schemas.module_definition import ModuleDefinition


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ModuleDiff:
    """Structural diff between two module versions."""

    version_from: str
    version_to: str
    breaking: bool = False  # True if upgrade requires user action

    # Config schema changes
    added_fields: list[dict[str, Any]] = field(default_factory=list)
    removed_fields: list[str] = field(default_factory=list)
    changed_fields: list[dict[str, Any]] = field(default_factory=list)

    # Port changes
    added_ports: list[dict[str, Any]] = field(default_factory=list)
    removed_ports: list[str] = field(default_factory=list)
    changed_ports: list[dict[str, Any]] = field(default_factory=list)

    # Provider policy changes
    provider_changes: dict[str, Any] | None = None

    # Metadata changes
    label_changed: bool = False
    description_changed: bool = False

    # Cost impact
    estimated_call_diff: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "versionFrom": self.version_from,
            "versionTo": self.version_to,
            "breaking": self.breaking,
            "addedFields": self.added_fields,
            "removedFields": self.removed_fields,
            "changedFields": self.changed_fields,
            "addedPorts": self.added_ports,
            "removedPorts": self.removed_ports,
            "changedPorts": self.changed_ports,
            "providerChanges": self.provider_changes,
            "labelChanged": self.label_changed,
            "descriptionChanged": self.description_changed,
            "estimatedCallDiff": self.estimated_call_diff,
        }


# ---------------------------------------------------------------------------
# Diff engine
# ---------------------------------------------------------------------------


def _get_schema_properties(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract the 'properties' dict from a configSchema."""
    return schema.get("properties", {})


def _diff_field(
    key: str, old_prop: dict[str, Any], new_prop: dict[str, Any]
) -> dict[str, Any] | None:
    """Compare two field property dicts.  Returns a change record or None."""
    changes: dict[str, Any] = {}
    for attr in ("type", "title", "default", "description"):
        old_val = old_prop.get(attr)
        new_val = new_prop.get(attr)
        if old_val != new_val:
            changes[attr] = {"from": old_val, "to": new_val}
    # Check enum / constraint changes
    for attr in ("enum", "minimum", "maximum", "pattern", "minLength", "maxLength"):
        old_val = old_prop.get(attr)
        new_val = new_prop.get(attr)
        if old_val != new_val:
            changes[attr] = {"from": old_val, "to": new_val}
    if changes:
        return {"field": key, "changes": changes}
    return None


def _diff_port(
    old_port: dict[str, Any], new_port: dict[str, Any]
) -> dict[str, Any] | None:
    """Compare two port definitions. Returns a change record or None."""
    changes: dict[str, Any] = {}
    for attr in ("type", "cardinality", "required", "label"):
        old_val = old_port.get(attr)
        new_val = new_port.get(attr)
        if old_val != new_val:
            changes[attr] = {"from": old_val, "to": new_val}
    if changes:
        return {"portId": old_port.get("id", ""), "changes": changes}
    return None


def _diff_provider_policy(
    old_policy: Any, new_policy: Any
) -> dict[str, Any] | None:
    """Compare two ProviderPolicy objects. Returns change record or None."""
    if old_policy is None and new_policy is None:
        return None

    changes: dict[str, Any] = {}
    attrs = ("capability", "allowed", "default", "locked")
    for attr in attrs:
        old_val = getattr(old_policy, attr, None) if old_policy else None
        new_val = getattr(new_policy, attr, None) if new_policy else None
        if old_val != new_val:
            changes[attr] = {"from": old_val, "to": new_val}
    return changes if changes else None


def _diff_variant_count(old_schema: dict, new_schema: dict) -> dict[str, Any] | None:
    """Compare variantCount defaults to estimate call count changes."""
    old_props = _get_schema_properties(old_schema)
    new_props = _get_schema_properties(new_schema)
    old_vc = old_props.get("variantCount", {})
    new_vc = new_props.get("variantCount", {})
    old_default = old_vc.get("default")
    new_default = new_vc.get("default")
    if old_default is not None and new_default is not None and old_default != new_default:
        return {"before": old_default, "after": new_default}
    return None


def compute_module_diff(old: ModuleDefinition, new: ModuleDefinition) -> ModuleDiff:
    """Compute structural diff between two module versions."""
    diff = ModuleDiff(version_from=old.version, version_to=new.version)

    # --- Config schema diff ---
    old_props = _get_schema_properties(old.config_schema)
    new_props = _get_schema_properties(new.config_schema)
    old_keys = set(old_props.keys())
    new_keys = set(new_props.keys())

    for key in sorted(new_keys - old_keys):
        field_info = dict(new_props[key])
        field_info["key"] = key
        diff.added_fields.append(field_info)

    for key in sorted(old_keys - new_keys):
        diff.removed_fields.append(key)

    for key in sorted(old_keys & new_keys):
        change = _diff_field(key, old_props[key], new_props[key])
        if change:
            diff.changed_fields.append(change)

    # --- Port diff ---
    for direction in ("inputs", "outputs"):
        old_ports = {p["id"]: p for p in old.ports.get(direction, [])}
        new_ports = {p["id"]: p for p in new.ports.get(direction, [])}

        for pid in sorted(set(new_ports.keys()) - set(old_ports.keys())):
            port_info = dict(new_ports[pid])
            port_info["direction"] = direction
            diff.added_ports.append(port_info)

        for pid in sorted(set(old_ports.keys()) - set(new_ports.keys())):
            diff.removed_ports.append(f"{direction}/{pid}")

        for pid in sorted(set(old_ports.keys()) & set(new_ports.keys())):
            change = _diff_port(old_ports[pid], new_ports[pid])
            if change:
                change["direction"] = direction
                diff.changed_ports.append(change)

    # --- Provider policy diff ---
    diff.provider_changes = _diff_provider_policy(
        old.provider_policy, new.provider_policy
    )

    # --- Metadata diff ---
    diff.label_changed = old.label != new.label
    diff.description_changed = old.description != new.description

    # --- Cost impact ---
    diff.estimated_call_diff = _diff_variant_count(
        old.config_schema, new.config_schema
    )

    # --- Breaking classification ---
    diff.breaking = is_breaking(diff)

    return diff


def is_breaking(diff: ModuleDiff) -> bool:
    """Determine if upgrade is breaking (requires user action).

    Breaking changes:
    - Removed config fields (existing overrides may reference them)
    - Removed ports (existing connections may reference them)
    - Type changes in fields (may break serialized config values)
    - Provider policy changes that restrict previously allowed providers
    """
    if diff.removed_fields:
        return True
    if diff.removed_ports:
        return True
    # Type changes are always breaking
    for change in diff.changed_fields:
        if "type" in change.get("changes", {}):
            return True
    # Provider restrictions
    if diff.provider_changes:
        allowed_changes = diff.provider_changes.get("allowed")
        if allowed_changes:
            old_allowed = set(allowed_changes.get("from", []) or [])
            new_allowed = set(allowed_changes.get("to", []) or [])
            if old_allowed - new_allowed:  # providers were removed
                return True
        locked_changes = diff.provider_changes.get("locked")
        if locked_changes:
            # locked changed from False to True — provider can no longer be swapped
            if locked_changes.get("from") is False and locked_changes.get("to") is True:
                return True
    return False


# ---------------------------------------------------------------------------
# Compatibility checker
# ---------------------------------------------------------------------------


def check_config_compatibility(
    old_config: dict[str, Any],
    old_schema: dict[str, Any],
    new_schema: dict[str, Any],
) -> list[str]:
    """Check if existing node config overrides are compatible with new schema.

    Returns a list of warning/error messages.  An empty list means the config
    is fully compatible.
    """
    messages: list[str] = []
    old_props = _get_schema_properties(old_schema)
    new_props = _get_schema_properties(new_schema)
    old_keys = set(old_props.keys())
    new_keys = set(new_props.keys())

    # Check for overrides referencing removed fields
    for key in old_config:
        if key in old_keys and key not in new_keys:
            messages.append(
                f"Warning: field '{key}' has been removed in the new version "
                f"but your config overrides it (value={old_config[key]!r}). "
                f"This override will be ignored."
            )

    # Check for type changes that break existing values
    for key in old_config:
        if key in old_keys and key in new_keys:
            old_type = old_props[key].get("type")
            new_type = new_props[key].get("type")
            if old_type != new_type:
                messages.append(
                    f"Error: field '{key}' type changed from "
                    f"'{old_type}' to '{new_type}'. "
                    f"Existing value {old_config[key]!r} may be incompatible."
                )

    return messages
