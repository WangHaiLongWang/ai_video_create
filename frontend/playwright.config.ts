import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright configuration for ai_video_create frontend E2E tests.
 *
 * The dev server is started automatically by Playwright when running tests.
 * Ensure the backend API is running at http://127.0.0.1:8000 before executing E2E tests,
 * as the Vite dev server proxies /api requests to it.
 */
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

  webServer: {
    command: 'npm run dev',
    port: 5173,
    reuseExistingServer: !process.env.CI,
    timeout: 15_000,
  },

  outputDir: 'test-results',
})
