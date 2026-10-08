import type { ModuleDefinition, PortError } from '../schemas/module-definition'

const API_BASE = '/api'

export class ModuleApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    /** Machine-readable code when the API returned one (e.g. "MODULE_VALIDATION_FAILED"). */
    public readonly code?: string,
    /** Structured validation errors (e.g. UNBOUND_MODULE_PORT) when present. */
    public readonly errors?: PortError[],
  ) {
    super(message)
    this.name = 'ModuleApiError'
  }
}

/** Shape of the FastAPI `detail` field on 4xx responses. */
interface ErrorDetail {
  code?: string
  message?: string
  errors?: Array<{ field?: string; error?: string; message?: string }>
}

async function parseResponse<T>(res: Response, action: string): Promise<T> {
  if (!res.ok) {
    let detail = `${action}: ${res.status}`
    let code: string | undefined
    let errors: PortError[] | undefined
    try {
      const payload = await res.json() as { detail?: string | ErrorDetail }
      if (typeof payload.detail === 'string') {
        detail = payload.detail
      } else if (payload.detail && typeof payload.detail === 'object') {
        // 422 validation body: { detail: { code, errors: [{field, error, message}] } }
        const obj = payload.detail
        code = obj.code
        if (Array.isArray(obj.errors)) {
          errors = obj.errors.map((e) => ({
            field: e.field ?? '',
            error: e.error ?? 'UNKNOWN',
            message: e.message ?? '',
          }))
        }
        if (errors && errors.length > 0) {
          detail = errors.map((e) => `${e.error}: ${e.field} - ${e.message}`).join('\n')
        } else if (obj.message) {
          detail = obj.message
        } else if (code) {
          detail = `${action}: ${code}`
        }
      }
    } catch {
      // Keep the status-based fallback for non-JSON responses.
    }
    throw new ModuleApiError(detail, res.status, code, errors)
  }
  return res.json() as Promise<T>
}

export async function fetchModules(status?: string, capability?: string): Promise<ModuleDefinition[]> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (capability) params.set('capability', capability)
  const res = await fetch(`${API_BASE}/modules?${params}`)
  return parseResponse(res, 'Failed to fetch modules')
}

export async function fetchModule(moduleId: string, version?: string): Promise<ModuleDefinition> {
  const url = version
    ? `${API_BASE}/modules/${moduleId}/versions/${version}`
    : `${API_BASE}/modules/${moduleId}`
  const res = await fetch(url)
  return parseResponse(res, 'Failed to fetch module')
}

export async function createModule(definition: ModuleDefinition): Promise<ModuleDefinition> {
  const res = await fetch(`${API_BASE}/modules`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(definition),
  })
  return parseResponse(res, 'Failed to create module')
}

export async function updateModule(
  definition: ModuleDefinition,
  expectedVersion: number,
): Promise<ModuleDefinition> {
  const res = await fetch(`${API_BASE}/modules/${encodeURIComponent(definition.id)}/draft`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ definition, expectedVersion }),
  })
  return parseResponse(res, 'Failed to update module')
}

export async function cloneModule(moduleId: string, version?: string, expectedVersion?: number): Promise<ModuleDefinition> {
  const res = await fetch(`${API_BASE}/modules/${moduleId}/clone`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version, expectedVersion }),
  })
  return parseResponse(res, 'Failed to clone module')
}

export async function publishModule(moduleId: string, version?: string, expectedVersion?: number): Promise<ModuleDefinition> {
  const res = await fetch(`${API_BASE}/modules/${moduleId}/publish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version, expectedVersion }),
  })
  return parseResponse(res, 'Failed to publish module')
}

export async function archiveModule(moduleId: string, version?: string, expectedVersion?: number): Promise<ModuleDefinition> {
  const res = await fetch(`${API_BASE}/modules/${moduleId}/archive`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version, expectedVersion }),
  })
  return parseResponse(res, 'Failed to archive module')
}
