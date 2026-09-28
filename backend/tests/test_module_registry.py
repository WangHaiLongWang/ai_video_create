"""Tests for Module Registry and Module API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.module_definition import ModuleDefinition, ProviderPolicy
from backend.app.schemas.node_manifest import ExecutionHints
from backend.app.services.module_registry import (
    ModuleRegistry,
    get_module_registry,
    BUILTIN_MODULES,
)


# ---------------------------------------------------------------------------
# Registry unit tests
# ---------------------------------------------------------------------------


class TestModuleRegistry:
    """Unit tests for ModuleRegistry."""

    def test_list_modules_returns_seedream(self):
        registry = ModuleRegistry()
        modules = registry.list_modules()
        ids = [m.id for m in modules]
        assert "builtin.seedream.text-to-image" in ids

    def test_list_modules_filter_by_status(self):
        registry = ModuleRegistry()
        published = registry.list_modules(status="published")
        assert all(m.status == "published" for m in published)
        draft = registry.list_modules(status="draft")
        assert all(m.status == "draft" for m in draft)

    def test_list_modules_filter_by_capability(self):
        registry = ModuleRegistry()
        image_modules = registry.list_modules(capability="image")
        assert len(image_modules) >= 1
        assert all(m.provider_policy.capability == "image" for m in image_modules)

    def test_get_module_by_id(self):
        registry = ModuleRegistry()
        module = registry.get_module("builtin.seedream.text-to-image")
        assert module is not None
        assert module.id == "builtin.seedream.text-to-image"
        assert module.label == "Seedream 文生图"
        assert module.base_kind == "textToImage"
        assert module.category == "image"

    def test_get_module_by_id_and_version(self):
        registry = ModuleRegistry()
        module = registry.get_module("builtin.seedream.text-to-image", version="1.0.0")
        assert module is not None
        assert module.version == "1.0.0"

    def test_get_module_nonexistent_returns_none(self):
        registry = ModuleRegistry()
        assert registry.get_module("nonexistent.module") is None

    def test_get_module_wrong_version_returns_none(self):
        registry = ModuleRegistry()
        assert registry.get_module("builtin.seedream.text-to-image", version="9.9.9") is None

    def test_latest_version_uses_semver_order(self):
        registry = ModuleRegistry()
        base = BUILTIN_MODULES["builtin.seedream.text-to-image"]
        for version in ("1.9.0", "1.10.0", "2.0.0-beta.1"):
            module = base.model_copy(update={"id": "test.semver", "version": version})
            registry._modules.setdefault(module.id, {})[version] = module
        assert registry.get_module("test.semver").version == "2.0.0-beta.1"

    def test_in_memory_clone_keeps_version_map_shape(self):
        registry = ModuleRegistry()
        clone = registry.clone_draft("builtin.seedream.text-to-image", "1.0.0")
        assert registry.get_module(clone.id, clone.version) == clone


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestModuleValidation:
    """Tests for validate_module."""

    def _make_valid_module(self) -> ModuleDefinition:
        return ModuleDefinition(
            id="test.module",
            version="1.0.0",
            baseKind="textToImage",
            category="image",
            label="Test Module",
        )

    def test_validate_module_accepts_valid_definition(self):
        registry = ModuleRegistry()
        module = self._make_valid_module()
        errors = registry.validate_module(module)
        assert errors == []

    def test_validate_module_rejects_missing_base_kind(self):
        registry = ModuleRegistry()
        module = ModuleDefinition(
            id="test.module",
            version="1.0.0",
            baseKind="",
            category="image",
            label="Test Module",
        )
        errors = registry.validate_module(module)
        assert any("base_kind" in e for e in errors)

    def test_validate_module_rejects_invalid_version_format(self):
        registry = ModuleRegistry()
        module = ModuleDefinition(
            id="test.module",
            version="not-a-version",
            baseKind="textToImage",
            category="image",
            label="Test Module",
        )
        errors = registry.validate_module(module)
        assert any("version" in e.lower() for e in errors)

    def test_validate_module_rejects_missing_id(self):
        registry = ModuleRegistry()
        module = ModuleDefinition(
            id="",
            version="1.0.0",
            baseKind="textToImage",
            category="image",
            label="Test Module",
        )
        errors = registry.validate_module(module)
        assert any("id" in e.lower() for e in errors)

    def test_validate_module_rejects_missing_label(self):
        registry = ModuleRegistry()
        module = ModuleDefinition(
            id="test.module",
            version="1.0.0",
            baseKind="textToImage",
            category="image",
            label="",
        )
        errors = registry.validate_module(module)
        assert any("label" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Config merge tests
# ---------------------------------------------------------------------------


class TestResolveEffectiveConfig:
    """Tests for resolve_effective_config."""

    def test_resolve_config_uses_defaults(self):
        registry = ModuleRegistry()
        config = registry.resolve_effective_config("builtin.seedream.text-to-image")
        assert config["provider"] == "doubao"
        assert config["image_model"] == "doubao-seedream-5-0-pro-260628"
        assert config["size"] == "1280x720"

    def test_resolve_config_merges_overrides(self):
        registry = ModuleRegistry()
        config = registry.resolve_effective_config(
            "builtin.seedream.text-to-image",
            instance_overrides={"size": "1920x1080", "seed": 42},
        )
        assert config["size"] == "1920x1080"
        assert config["seed"] == 42
        # Defaults still present
        assert config["provider"] == "doubao"

    def test_resolve_config_nonexistent_module_raises(self):
        registry = ModuleRegistry()
        with pytest.raises(KeyError):
            registry.resolve_effective_config("nonexistent.module")

    def test_resolve_config_uses_exact_version(self):
        registry = ModuleRegistry()
        base = BUILTIN_MODULES["builtin.seedream.text-to-image"]
        registry._modules["test.versioned"] = {
            "1.0.0": base.model_copy(update={"id": "test.versioned", "version": "1.0.0", "default_config": {"size": "small"}}),
            "2.0.0": base.model_copy(update={"id": "test.versioned", "version": "2.0.0", "default_config": {"size": "large"}}),
        }
        config = registry.resolve_effective_config("test.versioned", {"seed": 7}, version="1.0.0")
        assert config == {"size": "small", "seed": 7}


# ---------------------------------------------------------------------------
# Seedream built-in module data tests
# ---------------------------------------------------------------------------


class TestSeedreamBuiltin:
    """Validate the Seedream built-in module data is correct."""

    def test_seedream_is_published(self):
        module = BUILTIN_MODULES["builtin.seedream.text-to-image"]
        assert module.status == "published"

    def test_seedream_provider_policy(self):
        module = BUILTIN_MODULES["builtin.seedream.text-to-image"]
        pp = module.provider_policy
        assert pp.capability == "image"
        assert pp.allowed == ["doubao"]
        assert pp.default == "doubao"
        assert pp.locked is True

    def test_seedream_config_schema_has_required(self):
        module = BUILTIN_MODULES["builtin.seedream.text-to-image"]
        assert "image_model" in module.config_schema["required"]

    def test_seedream_default_config(self):
        module = BUILTIN_MODULES["builtin.seedream.text-to-image"]
        dc = module.default_config
        assert dc["provider"] == "doubao"
        assert dc["image_model"] == "doubao-seedream-5-0-pro-260628"
        assert dc["mapOver"] is True

    def test_seedream_execution_hints(self):
        module = BUILTIN_MODULES["builtin.seedream.text-to-image"]
        assert module.execution is not None
        assert module.execution.map_over == "scene"

    def test_seedream_ports(self):
        module = BUILTIN_MODULES["builtin.seedream.text-to-image"]
        input_ids = [p["id"] for p in module.ports["inputs"]]
        output_ids = [p["id"] for p in module.ports["outputs"]]
        assert "scene" in input_ids
        assert "image" in output_ids


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------


class TestModulesAPI:
    """Integration tests for the /api/modules endpoints."""

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        import backend.app.db.connection as connection
        import backend.app.services.module_registry as registry_module

        connection.close_connection()
        monkeypatch.setattr(connection, "_DB_PATH", tmp_path / "modules-api.db")
        registry_module._registry = None
        with TestClient(app) as test_client:
            yield test_client
        connection.close_connection()
        registry_module._registry = None

    def test_list_modules_returns_200(self, client):
        response = client.get("/api/modules")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_modules_contains_seedream(self, client):
        response = client.get("/api/modules")
        data = response.json()
        ids = [m["id"] for m in data]
        assert "builtin.seedream.text-to-image" in ids

    def test_list_modules_filter_status(self, client):
        response = client.get("/api/modules?status=published")
        assert response.status_code == 200
        data = response.json()
        assert all(m["status"] == "published" for m in data)

    def test_list_modules_filter_capability(self, client):
        response = client.get("/api/modules?capability=image")
        assert response.status_code == 200
        data = response.json()
        assert all(m["providerPolicy"]["capability"] == "image" for m in data)

    def test_capability_filter_uses_provider_policy_for_persisted_modules(self, client):
        common = {
            "version": "1.0.0",
            "status": "draft",
            "baseKind": "textToImage",
            "category": "custom",
            "providerPolicy": {"allowed": [], "default": None},
        }
        image_module = {
            **common,
            "id": "test.capability.image",
            "label": "Image capability",
            "providerPolicy": {**common["providerPolicy"], "capability": "image"},
        }
        video_module = {
            **common,
            "id": "test.capability.video",
            "label": "Video capability",
            "providerPolicy": {**common["providerPolicy"], "capability": "video"},
        }
        assert client.post("/api/modules", json=image_module).status_code == 201
        assert client.post("/api/modules", json=video_module).status_code == 201

        ids = {
            module["id"]
            for module in client.get("/api/modules?capability=video").json()
        }
        assert "test.capability.video" in ids
        assert "test.capability.image" not in ids

    def test_get_module_by_id(self, client):
        response = client.get("/api/modules/builtin.seedream.text-to-image")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "builtin.seedream.text-to-image"
        assert data["label"] == "Seedream 文生图"

    def test_get_module_by_id_and_version(self, client):
        response = client.get(
            "/api/modules/builtin.seedream.text-to-image/versions/1.0.0"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0"

    def test_get_module_nonexistent_returns_404(self, client):
        response = client.get("/api/modules/nonexistent.module")
        assert response.status_code == 404

    def test_get_module_wrong_version_returns_404(self, client):
        response = client.get(
            "/api/modules/builtin.seedream.text-to-image/versions/9.9.9"
        )
        assert response.status_code == 404

    def test_clone_module_returns_201(self, client):
        # Clone the built-in seedream module
        response = client.post("/api/modules/builtin.seedream.text-to-image/clone")
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "builtin.seedream.text-to-image-copy"
        assert data["version"] == "1.0.1"
        assert data["status"] == "draft"

    def test_clone_nonexistent_returns_404(self, client):
        response = client.post("/api/modules/nonexistent.module/clone")
        assert response.status_code == 404

    def test_publish_honors_expected_version(self, client):
        clone = client.post("/api/modules/builtin.seedream.text-to-image/clone").json()
        response = client.post(
            f"/api/modules/{clone['id']}/publish",
            json={"version": clone["version"], "expectedVersion": 99},
        )
        assert response.status_code == 409

    def test_publish_rejects_invalid_provider_policy(self, client):
        definition = {
            "id": "test.invalid-policy",
            "version": "1.0.0",
            "status": "draft",
            "baseKind": "textToImage",
            "category": "image",
            "label": "Invalid policy",
            "providerPolicy": {
                "capability": "image",
                "allowed": ["doubao"],
                "default": "openai",
                "locked": True,
            },
        }
        assert client.post("/api/modules", json=definition).status_code == 201
        response = client.post(
            "/api/modules/test.invalid-policy/publish",
            json={"version": "1.0.0", "expectedVersion": 1},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "MODULE_VALIDATION_FAILED"
