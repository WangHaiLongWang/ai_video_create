# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0-rc.1] - 2026-09-22

### Added
- **Browser E2E CI job**: Playwright Chromium tests run on every PR (Linux, Mock backend + Vite)
- **Three-platform CI**: Backend and Frontend jobs run on Windows, macOS, and Linux
- **AES-GCM secret encryption**: `cryptography` dependency for secure API key storage
- **Port-based graph validation**: Authoritative backend validation with self-loop, duplicate, type mismatch, cardinality, cycle, and direction checks
- **Agent v2 structured intent**: `WorkflowIntent` with validation, cost estimation, and repair steps
- **Scene JSON import/export**: Export/import scene bundles as JSON with scene_id, ordering, lock state, and prompts preserved
- **Doubao Seedream/Seedance provider**: Optional provider integration for ByteDance models
- **Variant fan-out**: Multi-variant image/video generation with scene_id::variant_id keying
- **Realistic Ski Lesson template**: 1-scene, 2-variant write-realistic workflow template

### Fixed
- **Port ID alignment** (RC-002): Backend `imageToVideo` output and `videoConcat` input now use singular `video` port, matching frontend canonical IDs
- **Pane click deselect** (RC-003A): E2E tests correctly target `.react-flow__pane` instead of `.react-flow__viewport`
- **Multi-node drag stability** (RC-003B): Hover-first approach, 8-step movement, click-before-drag for focus, and settling pauses prevent zero-delta drags
- **CI health probe**: Uses `/api/health` (correct path) instead of `/health`
- **CI integration tests**: Removed `|| true` that silently swallowed failures; external tests use `-m "not external"` marker
- **Pydantic deprecation**: Migrated `WorkflowSpec` from class-based `Config` to `ConfigDict`

### Changed
- **CI workflow restructured**: 4 jobs — `backend` (3 OS), `frontend` (3 OS), `integration` (Linux), `browser-e2e` (Linux)
- **Playwright config**: `reuseExistingServer: true` for local and CI environments
- **Mock provider edges**: All edge handles use canonical singular port IDs

### Test Results (baseline)
```
Backend:        1561 passed, 29 skipped, 0 failed
Acceptance:     170 passed, 0 failed
Frontend unit:  295+ passed
Browser E2E:    134 passed, 1 skipped (Chromium)
```

### Known Issues
- Pydantic V3 migration not yet complete (V2 `ConfigDict` used, V3 may require further changes)
- Doubao Seedream/Seedance provider integration is optional; not required for core workflow
- Scene roundtrip test requires backend running (skips gracefully when unavailable)
- Some performance and external provider tests are skipped by design in CI

## [1.0.0-beta.3] - 2026-09-18

### Added
- Scene Draft persistence with SQLite backend
- Scene Editor with lock/unlock, read-only mode, and add/delete scenes
- TaskPreview component for viewing generated images/videos
- Provider error UI — shows real error messages instead of faking success
- Undo/redo for canvas operations (viewport, selection, copy/paste)

### Fixed
- React Flow edge reconnection stability
- Dynamic port deletion cascading to associated edges
- Canvas zoom/pan target coordinates after viewport transform

## [1.0.0-beta.2] - 2026-09-15

### Added
- WorkflowSpec v2 typed node manifest with port-based validation
- Agent v1 → v2 migration path with structured intent
- Template service with SQLite persistence for custom templates
- 4 built-in templates: prompt-to-video, image-storyboard, quick-video, realistic-ski-lesson

### Fixed
- Template edge handles mismatch with frontend port IDs
- Agent compiler port reference consistency

## [1.0.0-beta.1] - 2026-09-10

### Added
- Initial React Flow canvas with custom studio nodes
- FastAPI backend with workflow CRUD, execution, and provider management
- Mock provider for offline development
- Basic CI pipeline (backend pytest, frontend build)
