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
    ],
  },
})
