import { defineConfig, devices } from '@playwright/test'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

/**
 * Playwright configuration for ai_video_create frontend E2E tests.
 *
 * Both servers are started by Playwright:
 *   1. Mock FastAPI backend on http://127.0.0.1:8000 (providers default to mock,
 *      database isolated via AI_VIDEO_DB_PATH so the dev DB is never polluted).
 *   2. Vite dev server on http://127.0.0.1:5173 (proxies /api to the backend).
 *
 * `reuseExistingServer: true` keeps CI working: the browser-e2e workflow already
 * boots both servers and Playwright simply attaches to them.
 */
const e2eDbPath = join(tmpdir(), `ai-video-create-e2e-${Date.now()}.db`)

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // sequential to avoid port conflicts on CI
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 1,
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
  ],
  timeout: 30_000,
  expect: { timeout: 5_000 },

  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: [
    {
      // Mock FastAPI backend — run-python.cjs resolves the project venv/python.
      command:
        'node ../scripts/run-python.cjs -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: true,
      timeout: 60_000,
      env: {
        // Preserve the ambient environment (PATH, etc.) and layer E2E settings.
        ...process.env,
        AI_VIDEO_DEFAULT_LLM_PROVIDER: 'mock',
        AI_VIDEO_DEFAULT_IMAGE_PROVIDER: 'mock',
        AI_VIDEO_DEFAULT_VIDEO_PROVIDER: 'mock',
        AI_VIDEO_DB_PATH: e2eDbPath,
        // Module E2E polls/queries enough endpoints to trip the 60/min limiter.
        DISABLE_RATE_LIMIT: '1',
      },
    },
    {
      command: 'npm run dev',
      port: 5173,
      // In CI, servers are started by the workflow; locally, reuse if already running.
      reuseExistingServer: true,
      timeout: 15_000,
    },
  ],

  outputDir: 'test-results',
})
