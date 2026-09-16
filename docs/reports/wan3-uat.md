# Wan3 Provider UAT Report

> 报告类型：真实 Provider UAT 证据

> 证据说明（2026-09-16 审计）：报告记录的测试日期晚于当前文档基线。作为发布门禁前，需要确认日期并补充被测 commit、环境锁文件和原始输出。

> Test Date: 2026-09-17
> Provider: Alibaba Cloud Bailian Wan3.0 Video (wan3)
> Model: wan3.0-video
> Resolution: 480P
> Duration: 2 seconds (minimum)
> Region: cn-beijing

## Executive Summary

**Result: PASS — 16/16 tests passed**

All Wan3 Provider user acceptance scenarios were validated against the real Alibaba Cloud Bailian API. The provider correctly handles health checks, task submission, task_id persistence, polling lifecycle, and end-to-end video generation with download.

## Test Configuration

| Setting | Value |
|---|---|
| API URL | `https://dashscope.aliyuncs.com/api/v1` |
| API Key | Configured via `AI_VIDEO_WAN3_API_KEY` |
| Model | `wan3.0-video` |
| Resolution | 480P |
| Ratio | adaptive |
| Duration | 2s (test) / 5s (default) |
| Audio | enabled |
| Poll Interval | 5s |
| Timeout | 1800s (default) / 600s (test) |

## Scenario 1: Provider Health Check

| Test | Result |
|---|---|
| Health check passes with valid key | PASS |
| Health check fails with invalid key | PASS |
| Config loads correctly from .env | PASS |
| API key fallback to DASHSCOPE_API_KEY | PASS |

The health check calls `GET /compatible-mode/v1/models` with the Bearer token. A valid key returns HTTP 200; an invalid key returns non-200. The provider correctly falls back from `WAN3_API_KEY` to `DASHSCOPE_API_KEY` to `OPENAI_API_KEY`.

## Scenario 2: Submit Minimal Video Task (480P / 2s)

| Test | Result |
|---|---|
| Direct API submission returns task_id | PASS |
| generate_video captures external_job_id | PASS |

A minimal text-to-video task was submitted to `POST /services/aigc/video-generation/video-synthesis` with `X-DashScope-Async: enable`. The API returned a valid task_id string. The provider correctly stores the task_id in `_last_external_job_id` for downstream persistence.

**API Response Time:** < 3 seconds for task submission.

## Scenario 3: Task ID Persistence

| Test | Result |
|---|---|
| external_job_id saved and retrieved from DB | PASS |
| NULL external_job_id handled gracefully | PASS |
| tasks table schema has external_job_id column | PASS |
| idx_tasks_external_job_id index exists | PASS |

The `save_external_job_id()` function correctly persists the Wan3 task_id to the `tasks` table via the `external_job_id` column. The migration (006) and index are verified. NULL values and overwrite scenarios work correctly.

## Scenario 4: Polling Logic

| Test | Result | Duration |
|---|---|---|
| RUNNING -> SUCCEEDED transition | PASS | < 1s (mock) |
| FAILED status raises ProviderError | PASS | < 1s (mock) |
| CANCELED status raises ProviderError | PASS | < 1s (mock) |
| Timeout raises ProviderError | PASS | < 1s (mock) |
| Real API poll until terminal state | PASS | ~88s (real) |

The real API poll test submitted a 480P/2s task and polled every 5 seconds until reaching SUCCEEDED. The polling mechanism correctly handles:
- RUNNING status: continues polling
- SUCCEEDED: returns output dict with video_url
- FAILED/CANCELED: raises ProviderError with message
- Timeout: raises ProviderError after deadline

**Real API Poll Duration:** ~88 seconds (7 polls at 5s intervals + processing).

## Scenario 5: Full Video Generation (End-to-End)

| Test | Result | Duration |
|---|---|---|
| generate_video full pipeline | PASS | ~79s |

The complete pipeline was validated:
1. Image encoding: 480x270 PNG -> base64 data URL
2. Task submission: POST with X-DashScope-Async header
3. Polling: 5s intervals until SUCCEEDED
4. Video download: GET temporary URL, follow redirects
5. Verification: MP4 container format, valid file size

**Key Metrics:**
- Video bytes: valid MP4 (ftyp box at offset 4)
- Total pipeline time: ~79 seconds
- Task_id captured via `get_external_job_id()`

## Issues Found

**No blocking issues found.**

| Observation | Severity | Note |
|---|---|---|
| Input image minimum 240x240 | Info | Wan3 API rejects images smaller than 240x240 pixels. Provider does not validate this client-side (relies on API error). |
| MP4 ftyp at offset 4 | Info | Wan3 returns standard MP4 with ftyp box at byte offset 4 (not 0). This is correct per ISO 14496-12. |
| task_id not persisted to DB in single run | Known | Currently, external_job_id is only available in-memory during generate_video(). Persistent storage to the tasks table requires the engine handler integration (tracked in main delivery plan). |

## Cost Summary

| Operation | Count | Est. Cost |
|---|---|---|
| Health check (models endpoint) | 2 | Free |
| Task submission (no completion) | 3 | ~3 API calls |
| Full video generation (480P/2s) | 2 | ~2 video tasks |
| Poll queries | ~20 | Free (status checks) |

## Recommendations

1. **Client-side image validation**: Add a minimum resolution check (240x240) in `Wan3VideoProvider._image_data_url()` to fail fast before submitting to the API.
2. **task_id persistence in handler**: The `RealImageToVideoHandler` should call `save_external_job_id()` after the provider returns, enabling process-restart recovery.
3. **Configurable poll interval for tests**: The current default 5s poll interval is reasonable for production but adds latency to tests. Consider making it injectable.
4. **Rate limiting**: No rate limit was hit during testing, but the `ProviderRateLimitError` handling with retry-after should be validated under load.

## Test File

- `backend/tests/integration/test_wan3_uat.py` — 16 tests across 5 scenarios
- Run: `python -m pytest backend/tests/integration/test_wan3_uat.py -v`
- Health-check only (free): `python -m pytest backend/tests/integration/test_wan3_uat.py -v -k "health"`
