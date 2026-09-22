import type { ModuleDefinition } from '../schemas/module-definition'

const API_BASE = '/api'

export async function fetchModules(status?: string, capability?: string): Promise<ModuleDefinition[]> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (capability) params.set('capability', capability)
  const res = await fetch(`${API_BASE}/modules?${params}`)
  if (!res.ok) throw new Error(`Failed to fetch modules: ${res.status}`)
  return res.json()
}

export async function fetchModule(moduleId: string, version?: string): Promise<ModuleDefinition> {
  const url = version
    ? `${API_BASE}/modules/${moduleId}/versions/${version}`
    : `${API_BASE}/modules/${moduleId}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to fetch module: ${res.status}`)
  return res.json()
}
