"""Integration tests for external_job_id persistence (Wan3 provider)."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.app.db.connection import close_connection, init_db, get_connection
from backend.app.engine.queue import (
    enqueue_tasks,
    get_task,
    save_external_job_id,
)
from backend.app.providers.wan3_provider import Wan3VideoProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Each test runs against an isolated in-memory-like SQLite database."""
    monkeypatch.setattr("backend.app.db.connection._DB_PATH", tmp_path / "test.db")
    close_connection()
    init_db()

    # Verify the migration ran successfully
    conn = get_connection()
    columns = [row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    assert "external_job_id" in columns, "Migration 006 did not add external_job_id column"

    # Create prerequisite records
    conn.execute(
        "INSERT INTO workflows (id, name, spec_json) VALUES (?, ?, ?)",
        ("wf-ext", "测试工作流", "{}"),
    )
    conn.execute(
        "INSERT INTO executions (id, workflow_id, workflow_snapshot, status) "
        "VALUES (?, ?, ?, ?)",
        ("exec-ext", "wf-ext", "{}", "running"),
    )
    conn.commit()
    yield
    close_connection()


# ---------------------------------------------------------------------------
# Tests: migration & column existence
# ---------------------------------------------------------------------------

class TestMigrationAddsColumn:
    def test_tasks_table_has_external_job_id_column(self):
        conn = get_connection()
        columns = [row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        assert "external_job_id" in columns

    def test_index_exists_on_external_job_id(self):
        conn = get_connection()
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='tasks' AND name='idx_tasks_external_job_id'"
        ).fetchall()
        assert len(indexes) == 1, "Expected idx_tasks_external_job_id index to exist"


# ---------------------------------------------------------------------------
# Tests: queue.save_external_job_id
# ---------------------------------------------------------------------------

class TestSaveExternalJobId:
    def test_save_external_job_id_updates_task(self):
        """save_external_job_id should write the value into the tasks row."""
        enqueue_tasks("wf-ext", "exec-ext", [
            {"id": "t-ext-1", "node_id": "n1", "kind": "imageToVideo",
             "label": "视频", "config": {}, "depends_on": []},
        ])

        save_external_job_id("t-ext-1", "wan3-task-abc-123")

        task = get_task("t-ext-1")
        assert task["external_job_id"] == "wan3-task-abc-123"

    def test_save_external_job_id_none_does_not_crash(self):
        """Passing None should still succeed (column accepts NULL)."""
        enqueue_tasks("wf-ext", "exec-ext", [
            {"id": "t-ext-2", "node_id": "n2", "kind": "imageToVideo",
             "label": "视频", "config": {}, "depends_on": []},
        ])
        save_external_job_id("t-ext-2", None)
        task = get_task("t-ext-2")
        assert task["external_job_id"] is None

    def test_save_external_job_id_overwrite(self):
        """Calling save_external_job_id twice should overwrite the first value."""
        enqueue_tasks("wf-ext", "exec-ext", [
            {"id": "t-ext-3", "node_id": "n3", "kind": "imageToVideo",
             "label": "视频", "config": {}, "depends_on": []},
        ])
        save_external_job_id("t-ext-3", "first-id")
        save_external_job_id("t-ext-3", "second-id")
        task = get_task("t-ext-3")
        assert task["external_job_id"] == "second-id"


# ---------------------------------------------------------------------------
# Tests: Wan3 provider get_external_job_id
# ---------------------------------------------------------------------------

class TestWan3ExternalJobId:
    def test_get_external_job_id_returns_none_before_generate(self):
        provider = Wan3VideoProvider("test-key")
        assert provider.get_external_job_id() is None

    @pytest.mark.asyncio
    async def test_get_external_job_id_after_generate(self, tmp_path: Path):
        """After generate_video the provider should expose the Wan3 task_id."""
        image = tmp_path / "frame.png"
        image.write_bytes(b"png-image-data")
        polls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal polls
            if request.url.path.endswith("/video-generation/video-synthesis"):
                return httpx.Response(200, json={
                    "output": {"task_id": "wan3-ext-job-999"}
                })
            if request.url.path.endswith("/tasks/wan3-ext-job-999"):
                polls += 1
                if polls == 1:
                    return httpx.Response(200, json={
                        "output": {"task_status": "RUNNING"}
                    })
                return httpx.Response(200, json={
                    "output": {
                        "task_status": "SUCCEEDED",
                        "video_url": "https://example.test/vid.mp4",
                    }
                })
            if request.url.path == "/vid.mp4":
                return httpx.Response(200, content=b"video-bytes")
            return httpx.Response(404)

        provider = Wan3VideoProvider("test-key")
        transport = httpx.MockTransport(handler)
        provider._client = httpx.AsyncClient(
            base_url="https://example.test/api/v1", transport=transport
        )

        original_client = httpx.AsyncClient

        class DownloadClient:
            def __init__(self, *a, **kw):
                self.client = original_client(transport=transport)
            async def __aenter__(self):
                return self.client
            async def __aexit__(self, *a):
                await self.client.aclose()

        import backend.app.providers.wan3_provider as mod
        mod.httpx.AsyncClient = DownloadClient
        try:
            await provider.generate_video(str(image), "测试", {"poll_interval": 0})
            assert provider.get_external_job_id() == "wan3-ext-job-999"
        finally:
            mod.httpx.AsyncClient = original_client
            await provider.close()


# ---------------------------------------------------------------------------
# Tests: full round-trip  (provider -> handler -> DB)
# ---------------------------------------------------------------------------

class TestEndToEndExternalJobId:
    """Simulate what the engine does: enqueue a task, run the handler, verify
    external_job_id is persisted in the database."""

    @pytest.mark.asyncio
    async def test_handler_persists_external_job_id(self, tmp_path: Path):
        from backend.app.handlers.real_handlers import RealImageToVideoHandler
        import backend.app.handlers.real_handlers as real_handlers_mod

        # Prepare a fake image file
        image_dir = tmp_path / "images"
        image_dir.mkdir()
        image_file = image_dir / "scene.png"
        image_file.write_bytes(b"fake-png")

        # Enqueue the task so save_external_job_id can update it
        enqueue_tasks("wf-ext", "exec-ext", [
            {"id": "t-e2e-1", "node_id": "n1", "kind": "imageToVideo",
             "label": "视频", "item_key": "scene-001", "config": {
                 "image_path": str(image_file),
                 "video_prompt": "镜头缓慢移动",
             }, "depends_on": []},
        ])

        # Mock the provider to simulate Wan3 behaviour
        mock_provider = MagicMock()
        mock_provider.capabilities = MagicMock()
        mock_provider.capabilities.video = True
        mock_provider.generate_video = AsyncMock(return_value=b"video-data")
        mock_provider.get_external_job_id = MagicMock(return_value="wan3-e2e-42")

        with patch.object(real_handlers_mod, "get_provider", return_value=mock_provider), \
             patch.object(real_handlers_mod, "get_asset_manager") as mock_am:
            mock_am.return_value.save_asset.return_value = "videos/vid-abc.mp4"
            mock_am.return_value.get_asset_path.side_effect = lambda p: str(tmp_path / p)
            mock_am.return_value.get_asset_url.return_value = "/assets/videos/vid-abc.mp4"

            handler = RealImageToVideoHandler()
            result = await handler.execute(
                {"id": "t-e2e-1", "item_key": "scene-001",
                 "config": {"image_path": str(image_file),
                            "video_prompt": "镜头缓慢移动",
                            "provider": "wan3"}},
                {"upstream_results": {}},
            )

        assert result.status == "succeeded"
        assert result.output is not None
        assert result.output.metadata["external_job_id"] == "wan3-e2e-42"

        # Verify it is actually stored in the DB
        task = get_task("t-e2e-1")
        assert task["external_job_id"] == "wan3-e2e-42"
