import { describe, expect, it, vi, beforeEach } from 'vitest'
import * as api from './api'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

function jsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
  }
}

describe('API client', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('fetchWorkflows calls GET /api/workflows', async () => {
    mockFetch.mockResolvedValue(jsonResponse([{ id: '1', name: 'test' }]))
    const result = await api.fetchWorkflows()
    expect(mockFetch).toHaveBeenCalledWith('/api/workflows', expect.objectContaining({
      headers: { 'Content-Type': 'application/json' },
    }))
    expect(result).toHaveLength(1)
  })

  it('createWorkflow calls POST with spec body', async () => {
    const spec = { id: 'new', name: 'new', nodes: [], edges: [] }
    mockFetch.mockResolvedValue(jsonResponse({ id: 'new', name: 'new', version: 1 }, 201))
    const result = await api.createWorkflow(spec)
    expect(mockFetch).toHaveBeenCalledWith('/api/workflows', expect.objectContaining({ method: 'POST' }))
    expect(result.id).toBe('new')
  })

  it('getWorkflow calls GET /api/workflows/:id', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ id: '1', spec: {} }))
    const result = await api.getWorkflow('1')
    expect(mockFetch).toHaveBeenCalledWith('/api/workflows/1', expect.anything())
    expect(result.id).toBe('1')
  })

  it('updateWorkflow calls PUT with version', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ id: '1', version: 2 }))
    const result = await api.updateWorkflow('1', { name: 'updated' }, 1)
    expect(mockFetch).toHaveBeenCalledWith('/api/workflows/1', expect.objectContaining({ method: 'PUT' }))
    const body = JSON.parse(mockFetch.mock.calls[0][1].body)
    expect(body.expected_version).toBe(1)
    expect(result.version).toBe(2)
  })

  it('deleteWorkflow calls DELETE', async () => {
    mockFetch.mockResolvedValue(jsonResponse(null, 204))
    await api.deleteWorkflow('1')
    expect(mockFetch).toHaveBeenCalledWith('/api/workflows/1', expect.objectContaining({ method: 'DELETE' }))
  })

  it('throws on non-OK response', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ detail: '未找到' }, 404))
    await expect(api.getWorkflow('missing')).rejects.toThrow('未找到')
  })
})
