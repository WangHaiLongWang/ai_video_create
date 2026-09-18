import { describe, expect, it, vi, beforeEach } from 'vitest'
import * as api from '../api'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

function jsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
  }
}

describe('Agent API functions', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('agentGeneratePreview calls POST /api/agent/generate-preview with prompt', async () => {
    const mockSpec = {
      id: 'wf-test',
      name: 'test',
      schemaVersion: '1.0',
      nodes: [],
      edges: [],
    }
    mockFetch.mockResolvedValue(jsonResponse({
      status: 'ok',
      spec: mockSpec,
      warnings: [],
      destructive: false,
    }))

    const result = await api.agentGeneratePreview('测试工作流')

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/agent/generate-preview',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ prompt: '测试工作流' }),
      }),
    )
    expect(result.status).toBe('ok')
    expect(result.spec).toBeDefined()
    expect(result.destructive).toBe(false)
  })

  it('agentModifyPreview calls POST /api/agent/modify-preview with workflow_id and instruction', async () => {
    const mockPatch = {
      description: '添加节点',
      add_nodes: [],
      remove_nodes: [],
      update_nodes: [],
      add_edges: [],
      remove_edges: [],
    }
    mockFetch.mockResolvedValue(jsonResponse({
      status: 'ok',
      patch: mockPatch,
      diff: '+ 新增 0 个节点',
      warnings: [],
      destructive: false,
    }))

    const result = await api.agentModifyPreview('wf-123', '添加一个输出节点')

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/agent/modify-preview',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          workflow_id: 'wf-123',
          instruction: '添加一个输出节点',
        }),
      }),
    )
    expect(result.patch).toBeDefined()
    expect(result.diff).toBeDefined()
  })

  it('agentApplyPatch calls POST /api/agent/apply-patch with expected_version', async () => {
    const mockSpec = {
      id: 'wf-123',
      name: 'test',
      schemaVersion: '1.0',
      nodes: [],
      edges: [],
    }
    mockFetch.mockResolvedValue(jsonResponse(mockSpec))

    const patch: api.GraphPatch = {
      description: '测试 patch',
      add_nodes: [],
      remove_nodes: ['n1'],
      update_nodes: [],
      add_edges: [],
      remove_edges: [],
    }

    const result = await api.agentApplyPatch('wf-123', patch, 2)

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/agent/apply-patch',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          workflow_id: 'wf-123',
          patch,
          expected_version: 2,
        }),
      }),
    )
    expect(result.id).toBe('wf-123')
  })

  it('agentApplyPatch omits expected_version when not provided', async () => {
    const mockSpec = {
      id: 'wf-123',
      name: 'test',
      schemaVersion: '1.0',
      nodes: [],
      edges: [],
    }
    mockFetch.mockResolvedValue(jsonResponse(mockSpec))

    const patch: api.GraphPatch = {
      description: '空 patch',
      add_nodes: [],
      remove_nodes: [],
      update_nodes: [],
      add_edges: [],
      remove_edges: [],
    }

    await api.agentApplyPatch('wf-123', patch)

    const body = JSON.parse(mockFetch.mock.calls[0][1].body)
    expect(body.expected_version).toBeUndefined()
  })

  it('agentGeneratePreview throws on error response', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ detail: '生成失败' }, 500))

    await expect(api.agentGeneratePreview('bad prompt')).rejects.toThrow('生成失败')
  })
})

describe('Agent v2 API functions', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('agentGeneratePreview_v2 calls POST /api/agent/generate-preview-v2', async () => {
    const mockResponse = {
      intent: { name: 'Test', nodes: [], connections: [] },
      compiled_workflow: null,
      validation_errors: [],
      repair_steps: [],
      cost_estimate: null,
      warnings: [],
      can_apply: true,
    }
    mockFetch.mockResolvedValue(jsonResponse(mockResponse))

    const result = await api.agentGeneratePreview_v2('测试工作流')

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/agent/generate-preview-v2',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ prompt: '测试工作流' }),
      }),
    )
    expect(result.intent.name).toBe('Test')
    expect(result.can_apply).toBe(true)
  })

  it('agentModifyPreview_v2 calls POST /api/agent/modify-preview-v2', async () => {
    const mockResponse = {
      intent: { name: 'Modified', nodes: [], connections: [] },
      compiled_workflow: null,
      validation_errors: [],
      repair_steps: [],
      cost_estimate: null,
      warnings: [],
      can_apply: true,
    }
    mockFetch.mockResolvedValue(jsonResponse(mockResponse))

    const result = await api.agentModifyPreview_v2('wf-123', '添加一个输出节点')

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/agent/modify-preview-v2',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          workflow_id: 'wf-123',
          instruction: '添加一个输出节点',
        }),
      }),
    )
    expect(result.intent.name).toBe('Modified')
  })

  it('agentApply_v2 calls POST /api/agent/apply-v2 with intent', async () => {
    const mockResponse = {
      success: true,
      workflow_id: 'wf-123',
      version: 2,
    }
    mockFetch.mockResolvedValue(jsonResponse(mockResponse))

    const intent: api.WorkflowIntent = {
      name: 'Test',
      nodes: [],
      connections: [],
    }

    const result = await api.agentApply_v2(intent, {
      workflowId: 'wf-123',
      expectedVersion: 1,
    })

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/agent/apply-v2',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          intent,
          workflow_id: 'wf-123',
          expected_version: 1,
        }),
      }),
    )
    expect(result.success).toBe(true)
    expect(result.version).toBe(2)
  })

  it('agentApply_v2 omits workflowId and expectedVersion when not provided', async () => {
    const mockResponse = { success: true, workflow_id: 'wf-new', version: 1 }
    mockFetch.mockResolvedValue(jsonResponse(mockResponse))

    const intent: api.WorkflowIntent = { name: 'New', nodes: [], connections: [] }
    await api.agentApply_v2(intent)

    const body = JSON.parse(mockFetch.mock.calls[0][1].body)
    expect(body.workflow_id).toBeNull()
    expect(body.expected_version).toBeNull()
  })

  it('agentApply_v2 returns error on failure', async () => {
    const mockResponse = { success: false, error: 'Validation failed' }
    mockFetch.mockResolvedValue(jsonResponse(mockResponse))

    const intent: api.WorkflowIntent = { name: 'Bad', nodes: [], connections: [] }
    const result = await api.agentApply_v2(intent)

    expect(result.success).toBe(false)
    expect(result.error).toBe('Validation failed')
  })
})
