// Polyfill structuredClone for Node < 17 / happy-dom environments
if (typeof globalThis.structuredClone === 'undefined') {
  globalThis.structuredClone = <T>(obj: T): T => JSON.parse(JSON.stringify(obj))
}
