# Changelog

All notable changes to the ai_video_create project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] - 2026-09-16

### Release Candidate - Feature Complete

Feature-complete release candidate with full execution engine, monitoring UI, and retry mechanisms.
This version marks the end of feature development; subsequent work focuses on testing and polish.

### Added

#### Execution Engine

- **Scheduler module** (`backend/app/engine/scheduler.py`): Core execution scheduler with
  topological task ordering, scene data injection, upstream output aggregation, and automatic
  execution convergence. Supports both manual (pending) and Worker (running) task completion modes.
  (37 acceptance tests passed)
- **Mock full-chain integration test** (`backend/tests/acceptance/test_mock_full_chain.py`):
  37 tests covering pipeline compilation, scene ID mapping, failure propagation, cancel operations,
  retry mechanisms, execution convergence, WorkerPool integration, and edge cases.

#### Retry & Resilience

- **Retry/backoff engine** (`backend/app/engine/retry.py`): Error classification (TRANSIENT,
  PERMANENT, RESOURCE, EXTERNAL, UNKNOWN), exponential backoff with jitter, 429 Retry-After
  extraction, and idempotency key support. (50 tests passed)
- **Single-node retry API** (`POST /api/executions/{execution_id}/retry`): Retry failed nodes
  with idempotency key deduplication. Returns 200/400/404/409 status codes. (8 API tests passed)
- **Migration 007**: Adds `error_code`, `next_retry_at`, and `idempotency_key` columns to tasks table.

#### Frontend Execution Monitoring

- **ExecutionPanel component** (`frontend/src/components/ExecutionPanel.tsx`): Real-time execution
  monitoring with node status list, progress tracking, error display, retry buttons, event log,
  and execution summary. (29 tests passed)
- **executionStore** (`frontend/src/stores/executionStore.ts`): Dedicated Zustand store for
  execution state management, separated from workflow store. Includes WebSocket integration
  and polling logic.

### Changed

- **store.ts refactored**: Execution-related state extracted to executionStore. Workflow store
  now focuses on canvas operations, history, and save/load.
- **TopBar.tsx updated**: Uses executionStore for run/stop buttons and status indicator.
- **queue.py enhanced**: `fail_task()` now supports `RetryPolicy` parameter, `claim_task()`
  skips tasks in backoff period, new `retry_node_task()` and `check_idempotency()` functions.

### Test Summary

| Category | Tests | Status |
|----------|-------|--------|
| Backend Pytest | 450 | ✅ Passed |
| Frontend Vitest | 63 | ✅ Passed |
| Wan3 UAT | 16 | ✅ Passed |
| FFmpeg Integration | 19 | ✅ Passed |
| **Total** | **548** | **✅ All Passed** |

## [0.1.0-rc.1] - 2026-09-15

### Release Candidate

First release candidate of ai_video_create, a prompt-to-video workflow engine
with AI-powered scene generation, image synthesis, and video production.

### Added

#### Execution Engine & Schema

- **NodeResult / ArtifactRef unified schema**: All handlers now return a standardized
  `NodeResult` containing `status`, `output`, `artifacts`, `metrics`, and `error`.
  Artifact tracking uses a consistent `ArtifactRef` with `kind`, `url`, `mime`,
  `sha256`, and `size` fields. (25 tests passed)
- **Dynamic scene mapping**: `expand_map_items()` in the compiler dynamically expands
  map tasks based on actual storyboard output. Worker assembles `NodeInput` by
  extracting the corresponding scene data via `scene_id` mapping.
- **Recursive failure propagation**: `fail_task()` uses a recursive CTE to propagate
  failure to all downstream tasks, ensuring no task remains permanently in `pending`
  state after an upstream failure.
- **Cancel race-condition fix**: `complete_task()` uses conditional updates
  (`WHERE status = 'running'`) to prevent completing a task that was concurrently
  cancelled. `cancel_task()` recursively cancels all downstream tasks via CTE.
  (13 tests passed)

#### Worker & Concurrency

- **2-4 Worker concurrent model**: `WorkerPool` manages multiple workers with atomic
  task claiming via `UPDATE ... WHERE status = 'pending' LIMIT 1`.
  Worker count is configurable via `AI_VIDEO_WORKER_COUNT` (range [1, 8]).
- **Worker lease and recovery**: Heartbeat and orphan detection functions ensure
  tasks are reclaimed when a worker crashes. Lease duration configurable via
  `AI_VIDEO_WORKER_LEASE_SECONDS`.

#### Wan3 Video Provider

- **external_job_id persistence**: Migration 006 adds `external_job_id` column to the
  `tasks` table. Long-running Wan3 tasks can survive process restarts by storing
  the external job identifier. `save_external_job_id()` and recovery polling implemented.
- **Wan3 real UAT passed (16/16 tests)**: All 16 user acceptance tests passed,
  covering 480P video generation, first-frame input, task polling, MP4 download,
  parameter validation, error handling, and edge cases.
- **Wan3 configuration**: Supports 480P/720P/1080P resolution, aspect ratio,
  duration, audio, seed, prompt extension, and watermark settings.

#### WebSocket & Real-time Updates

- **Frontend WebSocket client**: `ExecutionSocket` class with exponential backoff
  reconnection, `lastEventId` event replay, and connection status indicator.
  Backend WebSocket endpoint pushes execution events with 13 passing tests.

#### Agent & Template Integration

- **Agent backend**: `/api/agent/generate-preview`, `/api/agent/modify-preview`,
  `/api/agent/explain`, and `/api/agent/patch` endpoints with structured output.
  10 tests passed.
- **Agent frontend**: `AgentComposer` component connected to backend API, displays
  GraphPatch diffs, warnings, and confirmation flow. 5 tests passed.
- **Template system**: Built-in and SQLite-backed custom templates with
  `TemplateSelector` frontend component loading API-returned workflow specs.

#### Provider & LLM

- **OpenAI-compatible provider**: Custom LLM provider supporting arbitrary base URL,
  model name, authentication header/scheme, token parameter naming, temperature,
  top_p, max tokens, and timeout. Pre-configured for Xiaomi MiMo `mimo-v2.5-pro`.
- **Provider mixed configuration**: Independent registration of image (DashScope),
  video (Wan3), and text (OpenAI-compatible) providers. Each can be configured
  separately via environment variables or API.

#### Infrastructure

- **6 database migrations**: Initial schema, result column, assets table, templates
  table, attempt column, and external_job_id column.
- **Security middleware**: `SecurityMiddleware` and `InputSanitizeMiddleware` registered
  with basic headers, body size limits, and rate limiting.
- **Frontend build**: Vite production build producing optimized JS bundles
  (~124 KB gzipped).
- **Release check scripts**: Automated pre-release validation for Linux/macOS
  (`release-check.sh`) and Windows (`release-check.ps1`).

### Known Limitations

- FFmpeg not verified in this environment (6 tests skipped).
- Browser E2E tests not yet configured (Playwright pending).
- Provider settings are in-memory only; restart resets to `.env` values.
- ComfyUI img2vid workflow is a placeholder template.
- No macOS/Linux CI matrix evidence.
