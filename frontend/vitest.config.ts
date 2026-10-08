import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: [
      'e2e/**',
      'node_modules/**',
      'dist/**',
    ],
    environment: 'node',
    globals: true,
    setupFiles: ['src/test-setup.ts'],
    environmentMatchGlobs: [
      ['src/**/*.test.tsx', 'happy-dom'],
      ['src/components/**/*.test.ts', 'happy-dom'],
      // api tests use vi.spyOn(globalThis, 'fetch') / new Response() which need
      // browser globals absent from Node 16 (the local dev runtime).
      ['src/api/**/*.test.ts', 'happy-dom'],
    ],
    // EMFILE mitigation (RC-003): cap worker threads so parallel vite transforms
    // + happy-dom environments do not exhaust Windows file descriptors.
    // vitest 0.30.1 defaults to threads pool with maxThreads = CPU count.
    threads: true,
    maxThreads: 2,
    minThreads: 1,
  },
})
