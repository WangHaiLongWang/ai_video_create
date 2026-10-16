"""HARD-101 parity tests: schemas/base-node-manifest.json is the single source.

验收核心：
  - 后端 loader 与共享 JSON 逐字段一致（无漂移）
  - 端口 id/type/cardinality/required 与前端历史权威表冻结快照一致
  - 覆盖全部 NodeKind：textInput / storyboard / textToImage / imageToVideo /
    videoConcat / output
  - JSON Schema $defs 能校验 nodeKinds 数据
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.schemas.node_catalog import (
    get_manifest_path,
    get_node_manifest,
    list_node_kinds,
    list_node_manifests,
    load_manifest_document,
    load_node_catalog,
)
from backend.app.services.agent_tools import _NODE_CATALOG_V2

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "schemas" / "base-node-manifest.json"
FE_MANIFEST_TS = REPO_ROOT / "frontend" / "src" / "schemas" / "node-manifest.ts"

ALL_KINDS = (
    "textInput",
    "storyboard",
    "textToImage",
    "imageToVideo",
    "videoConcat",
    "output",
)

# ---------------------------------------------------------------------------
# 前端历史权威表（frontend/src/schemas/node-manifest.ts）端口契约冻结快照。
# 字段顺序：id / type / required / cardinality。
# 任何语义变更必须显式更新此快照并说明理由，禁止静默漂移。
# ---------------------------------------------------------------------------
FRONTEND_PORT_CONTRACT: dict[str, dict[str, list[tuple[str, str, bool, str]]]] = {
    "textInput": {
        "inputs": [],
        "outputs": [("text", "text", False, "one")],
    },
    "storyboard": {
        "inputs": [("prompt", "text", True, "one")],
        "outputs": [("scenes", "scene", False, "many")],
    },
    "textToImage": {
        "inputs": [("scene", "scene", True, "one")],
        "outputs": [("image", "image", False, "one")],
    },
    "imageToVideo": {
        "inputs": [
            ("image", "image", True, "one"),
            ("scene", "scene", False, "one"),
        ],
        "outputs": [("video", "video", False, "one")],
    },
    "videoConcat": {
        "inputs": [("video", "video", True, "many")],
        "outputs": [("video", "video", False, "one")],
    },
    "output": {
        # Output is an explicit polymorphic sink: video pipelines terminate on
        # ``video`` while image-only pipelines terminate on ``asset``.
        "inputs": [
            ("video", "video", False, "one"),
            ("asset", "any", False, "one"),
        ],
        "outputs": [],
    },
}


def _port_tuples(manifest) -> dict[str, list[tuple[str, str, bool, str]]]:
    def side(ports):
        return [(p.id, p.type, p.required, p.cardinality) for p in ports]

    return {
        "inputs": side(manifest.ports.inputs),
        "outputs": side(manifest.ports.outputs),
    }


def _port_tuples_from_raw(raw: dict) -> dict[str, list[tuple[str, str, bool, str]]]:
    def side(ports):
        return [
            (p["id"], p["type"], bool(p["required"]), p["cardinality"])
            for p in ports
        ]

    return {
        "inputs": side(raw["ports"]["inputs"]),
        "outputs": side(raw["ports"]["outputs"]),
    }


class TestSharedManifestDocument:
    def test_manifest_file_exists(self):
        assert MANIFEST_PATH.is_file(), f"missing {MANIFEST_PATH}"
        assert get_manifest_path() == MANIFEST_PATH

    def test_document_is_schema_and_data(self):
        doc = load_manifest_document()
        assert doc["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert doc["schemaVersion"] == "1.0"
        assert "NodeManifest" in doc["$defs"]
        assert "PortDefinition" in doc["$defs"]
        kinds = [n["kind"] for n in doc["nodeKinds"]]
        assert kinds == list(ALL_KINDS)

    def test_json_schema_validates_node_kinds(self):
        jsonschema = pytest.importorskip("jsonschema")
        doc = load_manifest_document()
        instance_schema = {
            "type": "array",
            "items": {"$ref": "#/$defs/NodeManifest"},
            "$defs": doc["$defs"],
        }
        jsonschema.Draft202012Validator(instance_schema).validate(doc["nodeKinds"])

    def test_each_port_has_required_fields(self):
        doc = load_manifest_document()
        for node in doc["nodeKinds"]:
            assert node["configSchema"] is not None, f"{node['kind']} missing configSchema"
            for side in ("inputs", "outputs"):
                for port in node["ports"][side]:
                    assert set(port) >= {"id", "type", "cardinality", "required"}
                    assert port["id"]
                    assert port["cardinality"] in ("one", "many")
                    if side == "outputs":
                        assert port["required"] is False, (
                            f"{node['kind']}.{port['id']} outputs must have required=false"
                        )


class TestLoaderParityNoDrift:
    def test_node_manifest_parity_no_drift(self):
        """loader / JSON / agent catalog / FE 冻结快照 四方一致。"""
        doc = load_manifest_document()
        catalog = load_node_catalog()
        raw_by_kind = {n["kind"]: n for n in doc["nodeKinds"]}

        assert list(catalog.keys()) == list(ALL_KINDS)
        for kind in ALL_KINDS:
            manifest = catalog[kind]
            raw = raw_by_kind[kind]
            assert manifest.kind == raw["kind"]
            assert manifest.version == raw["version"]
            assert manifest.category == raw["category"]
            assert manifest.label == raw["label"]
            assert manifest.description == raw["description"]
            assert manifest.config_schema == raw["configSchema"]
            assert _port_tuples(manifest) == _port_tuples_from_raw(raw)
            # 端口契约必须匹配前端权威表冻结快照
            assert _port_tuples(manifest) == FRONTEND_PORT_CONTRACT[kind]

    def test_image_to_video_output_cardinality_is_one(self):
        """历史漂移回归：imageToVideo 输出 cardinality 必须是 one。"""
        catalog = load_node_catalog()
        out = catalog["imageToVideo"].ports.outputs[0]
        assert out.id == "video"
        assert out.cardinality == "one"

    def test_text_to_image_port_id_is_image(self):
        """历史漂移回归：textToImage 输出端口 ID 必须是 image（不是 images）。"""
        catalog = load_node_catalog()
        assert catalog["textToImage"].ports.outputs[0].id == "image"

    def test_all_required_kinds_present(self):
        kinds = set(list_node_kinds())
        for kind in ALL_KINDS:
            assert kind in kinds

    def test_get_node_manifest(self):
        assert get_node_manifest("nope") is None
        for kind in ALL_KINDS:
            m = get_node_manifest(kind)
            assert m is not None
            assert m.kind == kind

    def test_list_node_manifests_order(self):
        assert [m.kind for m in list_node_manifests()] == list(ALL_KINDS)

    def test_agent_tools_catalog_uses_shared_loader(self):
        """agent_tools._NODE_CATALOG_V2 不得再是私有手写表。"""
        catalog = load_node_catalog()
        assert set(_NODE_CATALOG_V2.keys()) == set(catalog.keys())
        for kind, manifest in catalog.items():
            other = _NODE_CATALOG_V2[kind]
            assert _port_tuples(other) == _port_tuples(manifest)
            assert other.label == manifest.label
            assert other.category == manifest.category


class TestFrontendSourceWiring:
    def test_frontend_node_manifest_reads_shared_json(self):
        """前端 node-manifest.ts 必须引用共享 JSON，不得手写端口表。"""
        source = FE_MANIFEST_TS.read_text(encoding="utf-8")
        assert "base-node-manifest.json" in source
        # 禁止再出现手写 catalog 字面量里的端口定义
        assert "id: 'image'" not in source
        assert "id: 'scenes'" not in source

    def test_frontend_file_still_defines_types(self):
        source = FE_MANIFEST_TS.read_text(encoding="utf-8")
        assert "export interface NodeManifest" in source
        assert "export interface PortDefinition" in source
        assert "export const NODE_CATALOG" in source


class TestWorkflowFactoryPortIds:
    def test_node_port_ids_derived_from_catalog(self):
        from backend.app.workflow_factory import NODE_PORT_IDS

        catalog = load_node_catalog()
        for kind, manifest in catalog.items():
            in_id, out_id = NODE_PORT_IDS[kind]
            input_ids = [p.id for p in manifest.ports.inputs]
            output_ids = [p.id for p in manifest.ports.outputs]
            if in_id is not None:
                assert in_id in input_ids
            else:
                assert not input_ids
            if out_id is not None:
                assert out_id in output_ids
            else:
                assert not output_ids
