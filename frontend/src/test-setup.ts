import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom'

// Polyfill structuredClone for Node < 17 / happy-dom environments
if (typeof globalThis.structuredClone === 'undefined') {
  globalThis.structuredClone = <T>(obj: T): T => JSON.parse(JSON.stringify(obj))
}

// Serial-mode (--no-threads) stability: node-environment test files share one
// globalThis. Several tests call Object.defineProperty(globalThis, 'localStorage',
// { value: mock }), which creates a NON-configurable property on first
// definition; the next test file then throws "Cannot redefine property:
// localStorage". Pre-create the property as configurable so redefinition only
// swaps the value and leaves configurable: true intact (absent descriptor
// fields are preserved when the property is configurable).
try {
  Object.defineProperty(globalThis, 'localStorage', {
    value: (globalThis as { localStorage?: unknown }).localStorage,
    configurable: true,
    writable: true,
  })
} catch {
  // Already non-configurable from a previous definition; cannot fix here.
}

// Explicit RTL cleanup after every test.
// @testing-library/react auto-cleanup only self-registers when a global afterEach
// exists at module import time, which is unreliable under vitest 0.30
// --threads false / single-thread serial runs. Leftover DOM from earlier render()
// calls then makes screen.getBy* throw "Found multiple elements".
// cleanup() is a no-op when nothing was rendered; guard for node-environment
// tests (schema tests) where document is undefined.
afterEach(() => {
  if (typeof document !== 'undefined') {
    cleanup()
  }
})
