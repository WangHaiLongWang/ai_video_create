"""Shared ModuleDefinition/Workflow JSON Schema contract tests (HARD-102)."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from backend.app.models import WorkflowSpec
from backend.app.services.module_registry import BUILTIN_MODULES

ROOT = Path(__file__).resolve().parents[2]


def _schema(name: str) -> dict:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def test_builtin_modules_match_shared_schema():
    validator = Draft202012Validator(_schema("module-definition.schema.json"))
    for module in BUILTIN_MODULES.values():
        payload = module.model_dump(mode="json", by_alias=True)
        assert list(validator.iter_errors(payload)) == []


def test_workflow_pydantic_roundtrip_matches_shared_schema():
    payload = {
        "schemaVersion": "2.0", "manifestVersion": "1.0", "id": "wf-1", "name": "Workflow",
        "nodes": [{
            "id": "n1", "type": "studio", "position": {"x": 0, "y": 0},
            "data": {"label": "Input", "description": "", "kind": "textInput", "status": "idle", "config": {}},
        }],
        "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}, "metadata": {},
    }
    dumped = WorkflowSpec.model_validate(payload).model_dump(mode="json", by_alias=True)
    Draft202012Validator(_schema("workflow.schema.json")).validate(dumped)


def test_schema_files_are_valid_draft_2020_12():
    Draft202012Validator.check_schema(_schema("module-definition.schema.json"))
    Draft202012Validator.check_schema(_schema("workflow.schema.json"))
