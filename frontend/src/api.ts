/**
 * API 客户端 — 与后端 Workflow CRUD 交互。
 */

const BASE = '/api/workflows'

export interface WorkflowSummary {
  id: string
  name: string
  description: string
  version: number
  created_at: string
  updated_at: string
}

export interface WorkflowDetail extends WorkflowSummary {
  spec: Record<string, unknown>
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `请求失败 (${res.status})`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export function fetchWorkflows(): Promise<WorkflowSummary[]> {
  return request('')
}

export function getWorkflow(id: string): Promise<WorkflowDetail> {
  return request(`/${id}`)
}

export function createWorkflow(spec: Record<string, unknown>): Promise<WorkflowSummary> {
  return request('', { method: 'POST', body: JSON.stringify(spec) })
}

export function updateWorkflow(
  id: string,
  spec: Record<string, unknown>,
  expectedVersion: number,
): Promise<WorkflowSummary> {
  return request(`/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ spec, expected_version: expectedVersion }),
  })
}

export function deleteWorkflow(id: string): Promise<void> {
  return request(`/${id}`, { method: 'DELETE' })
}

export function duplicateWorkflow(id: string, name?: string): Promise<WorkflowSummary> {
  return request(`/${id}/duplicate`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export function exportWorkflow(id: string): Promise<{ spec: Record<string, unknown> }> {
  return request(`/${id}/export`, { method: 'POST' })
}

export function importWorkflow(spec: Record<string, unknown>): Promise<WorkflowSummary> {
  return request('/import', { method: 'POST', body: JSON.stringify(spec) })
}
