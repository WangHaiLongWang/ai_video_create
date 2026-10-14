/**
 * agentTrace API client tests — mocked fetch, pinned contract.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  AgentTraceApiError,
  getAgentTrace,
  listAgentTraces,
  type AgentTraceDetail,
  type AgentTraceSummary,
} from './agentTrace'

function summary(overrides?: Partial<AgentTraceSummary>): AgentTraceSummary {
  return {
    trace_id: 'trc-abc',
    workflow_id: 'wf-1',
    kind: 'generate',
    status: 'ok',
    error_code: null,
    prompt_hash: 'a'.repeat(64),
    provider: 'openai',
    model: 'gpt-4o',
    repair_count: 0,
    step_count: 3,
    duration_ms: 120,
    created_at: '2026-10-13T08:00:00Z',
    ...overrides,
  }
}

function detail(overrides?: Partial<AgentTraceDetail>): AgentTraceDetail {
  return {
    ...summary(),
    steps: [
      {
        step_id: 'stp-1',
        seq: 0,
        kind: 'parse',
        name: 'structured_intent',
        status: 'ok',
        duration_ms: 12,
        detail: {},
      },
    ],
    module_diff_summary: null,
    token_usage: null,
    ...overrides,
  }
}

describe('agentTrace API', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('listAgentTraces calls GET /api/agent/traces with default (no) query', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ traces: [], total: 0 }), { status: 200 }),
    )

    const result = await listAgentTraces()

    expect(fetchMock).toHaveBeenCalledWith('/api/agent/traces')
    expect(result).toEqual({ traces: [], total: 0 })
  })

  it('listAgentTraces serializes workflow_id, kind, limit, offset as query params', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ traces: [summary()], total: 1 }), { status: 200 }),
    )

    const result = await listAgentTraces({
      workflow_id: 'wf-1',
      kind: 'modify',
      limit: 10,
      offset: 5,
    })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/agent/traces?workflow_id=wf-1&kind=modify&limit=10&offset=5',
    )
    expect(result.traces).toHaveLength(1)
    expect(result.total).toBe(1)
  })

  it('listAgentTraces omits empty / undefined params', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ traces: [], total: 0 }), { status: 200 }),
    )

    await listAgentTraces({ kind: 'apply' })

    expect(fetchMock).toHaveBeenCalledWith('/api/agent/traces?kind=apply')
  })

  it('getAgentTrace calls GET /api/agent/traces/{trace_id}', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(detail()), { status: 200 }),
    )

    const result = await getAgentTrace('trc-abc')

    expect(fetchMock).toHaveBeenCalledWith('/api/agent/traces/trc-abc')
    expect(result.trace_id).toBe('trc-abc')
    expect(result.steps).toHaveLength(1)
  })

  it('getAgentTrace encodes the trace id', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(detail()), { status: 200 }),
    )

    await getAgentTrace('trc /weird')

    expect(fetchMock).toHaveBeenCalledWith('/api/agent/traces/trc%20%2Fweird')
  })

  it('404 surfaces TRACE_NOT_FOUND from the { error: { code, message } } body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ error: { code: 'TRACE_NOT_FOUND', message: 'trace not found' } }),
        { status: 404 },
      ),
    )

    await expect(getAgentTrace('trc-missing')).rejects.toMatchObject({
      name: 'AgentTraceApiError',
      status: 404,
      code: 'TRACE_NOT_FOUND',
      message: 'trace not found',
    })
  })

  it('AgentTraceApiError is instanceof Error with status + code', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ error: { code: 'TRACE_NOT_FOUND', message: 'gone' } }),
        { status: 404 },
      ),
    )

    let caught: unknown
    try {
      await getAgentTrace('trc-x')
    } catch (err) {
      caught = err
    }
    expect(caught).toBeInstanceOf(AgentTraceApiError)
    expect(caught).toBeInstanceOf(Error)
    expect((caught as AgentTraceApiError).code).toBe('TRACE_NOT_FOUND')
    expect((caught as AgentTraceApiError).status).toBe(404)
  })

  it('listAgentTraces throws AgentTraceApiError on non-OK response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'INTERNAL', message: 'boom' } }), {
        status: 500,
      }),
    )

    await expect(listAgentTraces()).rejects.toMatchObject({
      name: 'AgentTraceApiError',
      status: 500,
      code: 'INTERNAL',
      message: 'boom',
    })
  })
})
