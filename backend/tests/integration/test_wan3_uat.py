"""Wan3 Provider Real UAT (User Acceptance Testing).

Test Scenarios:
  1. Health Check — verify API key validity via the models endpoint.
  2. Submit Minimal Video Task — 480P / 2s video, verify task_id returned.
  3. Task ID Persistence — save external_job_id to DB, verify retrieval.
  4. Polling Logic — poll until terminal state (SUCCEEDED / FAILED).
  5. Full Video Generation (optional) — download and verify video bytes.

Run (includes real API calls, costs money):
    cd d:/ProjectS/ai_video_create
    python -m pytest backend/tests/integration/test_wan3_uat.py -v

Run health-check only (free, fast):
    python -m pytest backend/tests/integration/test_wan3_uat.py -v -k "health"
"""

from __future__ import annotations

import asyncio
import io
import time
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from PIL import Image

from backend.app.config import Settings, get_settings, reset_settings
from backend.app.db.connection import close_connection, get_connection, init_db
from backend.app.engine.queue import (
    enqueue_tasks,
    get_task,
    save_external_job_id,
)
from backend.app.providers.base import (
    ProviderConnectionError,
    ProviderError,
    ProviderNotConfiguredError,
)
from backend.app.providers.wan3_provider import Wan3VideoProvider

# ---------------------------------------------------------------------------
# Markers & Constants
# ---------------------------------------------------------------------------

uat = pytest.mark.skipif(
    True,  # 额度不足，暂时跳过所有真实 API 调用的 UAT 测试
    reason="Quota exhausted — skipping real Wan3/Qwen API calls",
)

WAN3_API_KEY = get_settings().WAN3_API_KEY
WAN3_API_URL = get_settings().WAN3_API_URL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_png(tmp_path: Path) -> str:
    """Create a valid 480x270 RGB PNG image for the Wan3 API.

    The Wan3 API requires input images to be at least 240x240 pixels.
    We use 480x270 (16:9) to match the default 'adaptive' ratio at 480P.
    """
    img_path = tmp_path / "test_frame.png"
    img = Image.new("RGB", (480, 270), color=(100, 149, 237))
    img.save(str(img_path), format="PNG")
    return str(img_path)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def provider() -> Wan3VideoProvider:
    """Create a real Wan3VideoProvider from the .env configuration."""
    settings = get_settings()
    assert settings.WAN3_API_KEY, (
        "WAN3_API_KEY is empty. Set AI_VIDEO_WAN3_API_KEY in .env."
    )
    return Wan3VideoProvider(
        api_key=settings.WAN3_API_KEY,
        api_url=settings.WAN3_API_URL,
        model="wan3.0-video",
        default_config={
            "resolution": "480P",
            "ratio": "adaptive",
            "duration": 5,
            "audio": True,
            "seed": -1,
            "prompt_extend": True,
            "watermark": False,
            "poll_interval": 5,
            "timeout": 1800,
        },
    )


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    """Each test runs against an isolated SQLite database."""
    monkeypatch.setattr("backend.app.db.connection._DB_PATH", tmp_path / "test.db")
    close_connection()
    init_db()
    yield
    close_connection()


# ===========================================================================
# Scenario 1: Provider Health Check
# ===========================================================================


class TestScenario1_HealthCheck:
    """Verify the Wan3 API key is valid by calling the models endpoint."""

    @uat
    @pytest.mark.asyncio
    async def test_health_check_passes_with_valid_key(self, provider: Wan3VideoProvider):
        """The health check should return True when the API key is valid."""
        result = await provider.health_check()
        assert result is True, "Wan3 health check failed — API key may be invalid"
        await provider.close()

    @uat
    @pytest.mark.asyncio
    async def test_health_check_fails_with_bad_key(self):
        """A provider with an invalid key should fail the health check."""
        bad_provider = Wan3VideoProvider(
            api_key="sk-invalid-key-that-should-not-work-12345",
            api_url=WAN3_API_URL,
            model="wan3.0-video",
        )
        result = await bad_provider.health_check()
        assert result is False, "Health check should fail with an invalid key"
        await bad_provider.close()

    def test_config_loads_correctly(self):
        """Verify the Wan3 config is loaded from Settings correctly."""
        settings = get_settings()
        assert settings.WAN3_MODEL == "wan3.0-video"
        assert settings.WAN3_RESOLUTION == "480P"
        assert settings.WAN3_RATIO == "adaptive"
        assert settings.WAN3_DURATION == 5
        assert settings.WAN3_AUDIO is True
        assert settings.WAN3_SEED == -1
        assert settings.WAN3_PROMPT_EXTEND is True
        assert settings.WAN3_WATERMARK is False
        assert settings.WAN3_POLL_INTERVAL == 5.0
        assert settings.WAN3_TIMEOUT == 1800

    def test_provider_config_fallback_to_dashscope_key(self):
        """If WAN3_API_KEY is empty, it should fall back to DASHSCOPE_API_KEY."""
        settings = Settings(
            WAN3_API_KEY="",
            DASHSCOPE_API_KEY="fallback-key-123",
            OPENAI_API_KEY="openai-key-456",
        )
        config = settings.get_provider_config(settings.DEFAULT_VIDEO_PROVIDER)
        # When DEFAULT_VIDEO_PROVIDER is mock, we need to explicitly get wan3 config
        from backend.app.config import ProviderType

        wan3_config = settings.get_provider_config(ProviderType.WAN3)
        assert wan3_config.api_key == "fallback-key-123"


# ===========================================================================
# Scenario 2: Submit Minimal 480P / 2-second Video Task
# ===========================================================================


class TestScenario2_SubmitVideoTask:
    """Submit the smallest possible Wan3 video task and verify the API response."""

    @uat
    @pytest.mark.asyncio
    async def test_submit_minimal_task_returns_task_id(self, provider: Wan3VideoProvider):
        """Submit a 480P / 2-second text-to-video task. Verify task_id is returned."""
        config = {
            "resolution": "480P",
            "ratio": "adaptive",
            "duration": 2,  # minimum allowed
            "audio": True,
            "seed": -1,
            "prompt_extend": False,
            "watermark": False,
            "poll_interval": 5,
            "timeout": 300,
        }

        # Directly call the API to submit the task without polling to completion.
        # We use the provider's internal methods to verify the submission step only.
        client = await provider._get_client()
        response = await client.post(
            "/services/aigc/video-generation/video-synthesis",
            headers={"X-DashScope-Async": "enable"},
            json={
                "model": "wan3.0-video",
                "input": {
                    "prompt": "A calm ocean with gentle waves, soft sunlight",
                },
                "parameters": {
                    "resolution": "480P",
                    "ratio": "adaptive",
                    "duration": 2,
                    "audio": True,
                    "seed": -1,
                    "prompt_extend": False,
                    "watermark": False,
                },
            },
        )

        assert response.status_code == 200, (
            f"Wan3 task submission failed: {response.status_code} {response.text}"
        )
        body = response.json()
        task_id = body.get("output", {}).get("task_id")
        assert task_id is not None, f"No task_id in response: {body}"
        assert len(task_id) > 0, "task_id is empty"
        provider._last_external_job_id = str(task_id)

        # Verify the task_id format (Wan3 returns a string ID)
        assert isinstance(task_id, (str, int)), f"Unexpected task_id type: {type(task_id)}"
        print(f"\n  [UAT] Task submitted: task_id={task_id}")

        await provider.close()

    @uat
    @pytest.mark.asyncio
    async def test_submit_task_via_generate_video(self, provider: Wan3VideoProvider, tmp_path: Path):
        """Submit via generate_video and verify external_job_id is set after submission."""
        img_path = _make_valid_png(tmp_path)

        # Override poll interval to a short value so we don't wait too long,
        # but we only need to verify that the task was submitted and polling started.
        task_id_holder: dict[str, str | None] = {}

        original_poll = provider._poll_task

        async def capture_poll(client, task_id, timeout, poll_interval):
            task_id_holder["task_id"] = task_id
            # Cancel immediately to avoid long wait — just verify task was submitted
            raise ProviderError("wan3", "UAT: poll cancelled to test submission only")

        provider._poll_task = capture_poll  # type: ignore

        try:
            with pytest.raises(ProviderError, match="UAT: poll cancelled"):
                await provider.generate_video(
                    img_path,
                    "A calm ocean with gentle waves",
                    {
                        "duration": 2,
                        "resolution": "480P",
                        "ratio": "adaptive",
                        "audio": True,
                        "seed": -1,
                        "prompt_extend": False,
                        "watermark": False,
                        "poll_interval": 5,
                        "timeout": 300,
                    },
                )
        finally:
            provider._poll_task = original_poll  # type: ignore
            await provider.close()

        # Verify that a real task_id was returned by the API
        task_id = task_id_holder.get("task_id")
        assert task_id is not None, "No task_id was captured from the API submission"
        assert provider.get_external_job_id() == task_id
        print(f"\n  [UAT] Task submitted via generate_video: task_id={task_id}")


# ===========================================================================
# Scenario 3: Verify task_id Persistence
# ===========================================================================


class TestScenario3_TaskIdPersistence:
    """Verify external_job_id can be saved to and retrieved from the DB."""

    def _setup_db_records(self):
        """Create prerequisite workflow and execution records."""
        conn = get_connection()
        conn.execute(
            "INSERT INTO workflows (id, name, spec_json) VALUES (?, ?, ?)",
            ("wf-uat", "UAT 工作流", "{}"),
        )
        conn.execute(
            "INSERT INTO executions (id, workflow_id, workflow_snapshot, status) "
            "VALUES (?, ?, ?, ?)",
            ("exec-uat", "wf-uat", "{}", "running"),
        )
        conn.commit()

    @uat
    def test_external_job_id_persisted_and_retrieved(self):
        """Save a Wan3 task_id to the DB and verify it can be read back."""
        self._setup_db_records()
        enqueue_tasks("wf-uat", "exec-uat", [
            {
                "id": "uat-task-1",
                "node_id": "i2v-1",
                "kind": "imageToVideo",
                "label": "UAT 视频",
                "config": {},
                "depends_on": [],
            },
        ])

        wan3_task_id = "dashscope-task-uat-test-abc123"
        save_external_job_id("uat-task-1", wan3_task_id)

        task = get_task("uat-task-1")
        assert task["external_job_id"] == wan3_task_id, (
            f"external_job_id not persisted: got {task['external_job_id']!r}"
        )

    @uat
    def test_external_job_id_survives_null_update(self):
        """Ensure the column handles None gracefully."""
        self._setup_db_records()
        enqueue_tasks("wf-uat", "exec-uat", [
            {
                "id": "uat-task-2",
                "node_id": "i2v-2",
                "kind": "imageToVideo",
                "label": "UAT 视频 2",
                "config": {},
                "depends_on": [],
            },
        ])

        save_external_job_id("uat-task-2", None)
        task = get_task("uat-task-2")
        assert task["external_job_id"] is None

        # Now save a real value and verify overwrite
        save_external_job_id("uat-task-2", "real-task-id-456")
        task = get_task("uat-task-2")
        assert task["external_job_id"] == "real-task-id-456"

    def test_schema_has_external_job_id_column(self):
        """Verify the migration added the external_job_id column."""
        conn = get_connection()
        columns = [row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        assert "external_job_id" in columns

    def test_index_exists_on_external_job_id(self):
        """Verify the index on external_job_id exists."""
        conn = get_connection()
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='tasks' AND name='idx_tasks_external_job_id'"
        ).fetchall()
        assert len(indexes) == 1


# ===========================================================================
# Scenario 4: Verify Polling Logic
# ===========================================================================


class TestScenario4_PollingLogic:
    """Verify the polling mechanism correctly handles all task lifecycle states."""

    @pytest.mark.asyncio
    async def test_poll_succeeds_on_running_then_succeeded(self, provider: Wan3VideoProvider):
        """Poll should return output when task transitions from RUNNING to SUCCEEDED."""
        polls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal polls
            if request.url.path.endswith("/tasks/poll-test-ok"):
                polls += 1
                if polls == 1:
                    return httpx.Response(200, json={
                        "output": {"task_status": "RUNNING"},
                    })
                return httpx.Response(200, json={
                    "output": {
                        "task_status": "SUCCEEDED",
                        "video_url": "https://example.test/v.mp4",
                    },
                })
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(
            base_url="https://mock.api/api/v1", transport=transport
        )

        output = await provider._poll_task(
            client, "poll-test-ok", timeout=30, poll_interval=0.01
        )

        assert output["task_status"] == "SUCCEEDED"
        assert output["video_url"] == "https://example.test/v.mp4"
        assert polls == 2
        await client.aclose()

    @pytest.mark.asyncio
    async def test_poll_raises_on_failed_status(self, provider: Wan3VideoProvider):
        """Poll should raise ProviderError when task_status is FAILED."""
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "output": {
                    "task_status": "FAILED",
                    "message": "Content policy violation",
                },
            })

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(
            base_url="https://mock.api/api/v1", transport=transport
        )

        with pytest.raises(ProviderError, match="Content policy violation"):
            await provider._poll_task(
                client, "poll-test-fail", timeout=30, poll_interval=0.01
            )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_poll_raises_on_canceled_status(self, provider: Wan3VideoProvider):
        """Poll should raise ProviderError when task_status is CANCELED."""
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "output": {"task_status": "CANCELED"},
            })

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(
            base_url="https://mock.api/api/v1", transport=transport
        )

        with pytest.raises(ProviderError):
            await provider._poll_task(
                client, "poll-test-cancel", timeout=30, poll_interval=0.01
            )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_poll_raises_on_timeout(self, provider: Wan3VideoProvider):
        """Poll should raise ProviderError when the timeout is exceeded."""
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "output": {"task_status": "RUNNING"},
            })

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(
            base_url="https://mock.api/api/v1", transport=transport
        )

        start = time.monotonic()
        with pytest.raises(ProviderError, match="timed out"):
            await provider._poll_task(
                client, "poll-test-timeout", timeout=0.1, poll_interval=0.05
            )
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"Poll timeout took too long: {elapsed:.1f}s"
        await client.aclose()

    @uat
    @pytest.mark.asyncio
    async def test_real_poll_returns_terminal_status(self, provider: Wan3VideoProvider, tmp_path: Path):
        """Submit a real task and poll until it reaches a terminal state.

        This test costs money (video generation) and can take 1-5 minutes.
        It verifies the full polling lifecycle with the real Wan3 API.
        """
        img_path = _make_valid_png(tmp_path)
        client = await provider._get_client()

        # Submit a minimal 2-second task
        submit_resp = await client.post(
            "/services/aigc/video-generation/video-synthesis",
            headers={"X-DashScope-Async": "enable"},
            json={
                "model": "wan3.0-video",
                "input": {
                    "prompt": "Gentle waves on a sandy beach",
                },
                "parameters": {
                    "resolution": "480P",
                    "ratio": "adaptive",
                    "duration": 2,
                    "audio": True,
                    "seed": -1,
                    "prompt_extend": False,
                    "watermark": False,
                },
            },
        )
        assert submit_resp.status_code == 200
        task_id = submit_resp.json()["output"]["task_id"]
        provider._last_external_job_id = str(task_id)
        print(f"\n  [UAT] Real task submitted: task_id={task_id}")

        # Poll until terminal state
        terminal_states = {"SUCCEEDED", "FAILED", "CANCELED", "CANCELLED", "UNKNOWN"}
        deadline = time.monotonic() + 300  # 5-minute hard limit for UAT
        poll_count = 0
        final_status = None

        while time.monotonic() < deadline:
            poll_count += 1
            status_resp = await client.get(f"/tasks/{task_id}")
            assert status_resp.status_code == 200
            body = status_resp.json()
            output = body.get("output", {})
            status = str(output.get("task_status", "")).upper()
            elapsed = time.monotonic() - (deadline - 300)
            print(f"  [UAT] Poll #{poll_count}: status={status} ({elapsed:.0f}s elapsed)")

            if status in terminal_states:
                final_status = status
                break

            await asyncio.sleep(5)

        assert final_status is not None, "Task did not reach terminal state within 5 minutes"
        print(f"\n  [UAT] Task completed: status={final_status} after {poll_count} polls")

        if final_status == "SUCCEEDED":
            video_url = output.get("video_url")
            results = output.get("results", [])
            if not video_url and results:
                video_url = results[0].get("video_url") or results[0].get("url")
            assert video_url is not None, "SUCCEEDED but no video_url in output"
            print(f"  [UAT] Video URL: {video_url}")

        await provider.close()


# ===========================================================================
# Scenario 5: Full Video Generation (optional, most expensive)
# ===========================================================================


class TestScenario5_FullVideoGeneration:
    """End-to-end video generation — submit, poll, download, verify bytes.

    This is the most expensive UAT scenario. It verifies the complete pipeline.
    """

    @uat
    @pytest.mark.asyncio
    async def test_generate_video_full_pipeline(self, provider: Wan3VideoProvider, tmp_path: Path):
        """Generate a 480P / 2-second video and download the result bytes."""
        img_path = _make_valid_png(tmp_path)

        video_bytes = await provider.generate_video(
            img_path,
            "Gentle waves on a sandy beach under blue sky",
            {
                "duration": 2,
                "resolution": "480P",
                "ratio": "adaptive",
                "audio": True,
                "seed": 42,
                "prompt_extend": False,
                "watermark": False,
                "poll_interval": 5,
                "timeout": 600,
            },
        )

        # Verify video bytes
        assert isinstance(video_bytes, bytes), f"Expected bytes, got {type(video_bytes)}"
        assert len(video_bytes) > 1000, (
            f"Video too small: {len(video_bytes)} bytes — likely not a valid video"
        )

        # Verify MP4 magic bytes — standard MP4 has 'ftyp' at offset 4
        # (bytes 0-3 are the box size, bytes 4-7 are the box type)
        assert len(video_bytes) >= 8, f"Video too short: {len(video_bytes)} bytes"
        ftyp_at_0 = video_bytes[:4] == b"ftyp"
        ftyp_at_4 = video_bytes[4:8] == b"ftyp"
        assert ftyp_at_0 or ftyp_at_4, (
            f"Not a valid MP4: bytes[0:4]={video_bytes[:4]!r}, bytes[4:8]={video_bytes[4:8]!r}"
        )

        # Verify external_job_id is set
        ext_job_id = provider.get_external_job_id()
        assert ext_job_id is not None, "external_job_id not set after generate_video"
        print(
            f"\n  [UAT] Video generated successfully: "
            f"{len(video_bytes)} bytes, task_id={ext_job_id}"
        )

        # Save to disk for manual inspection
        output_path = tmp_path / "uat_video.mp4"
        output_path.write_bytes(video_bytes)
        print(f"  [UAT] Saved to: {output_path}")

        await provider.close()
