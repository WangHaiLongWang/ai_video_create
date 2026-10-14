/**
 * AgentTracePanel 单元测试
 *
 * 覆盖:
 * 1. 列表渲染（mock listAgentTraces）
 * 2. kind 过滤重新发起请求
 * 3. 选中行 → 拉取详情，步骤按 seq 排序
 * 4. module_diff_summary / token_usage 有值渲染、为 null 隐藏
 * 5. prompt_hash 截断，列表不出现完整 64 字符原文
 * 6. 404 TRACE_NOT_FOUND → 错误态
 * 7. 空列表 → 空态
 * 8. detail 中的 sk-... 密钥不被二次展示
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { AgentTracePanel } from './AgentTracePanel'
import {
  AgentTraceApiError,
  getAgentTrace,
  listAgentTraces,
  type AgentTraceDetail,
  type AgentTraceSummary,
} from '../api/agentTrace'

vi.mock('../api/agentTrace', async () => {
  const actual = await vi.importActual<typeof import('../api/agentTrace')>('../api/agentTrace')
  return {
    ...actual,
    listAgentTraces: vi.fn(),
    getAgentTrace: vi.fn(),
  }
})

const FULL_HASH = 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2'

function makeSummary(overrides?: Partial<AgentTraceSummary>): AgentTraceSummary {
  return {
    trace_id: 'trc-1',
    workflow_id: 'wf-1',
    kind: 'generate',
    status: 'ok',
    error_code: null,
    prompt_hash: FULL_HASH,
    provider: 'openai',
    model: 'gpt-4o',
    repair_count: 1,
    step_count: 3,
    duration_ms: 450,
    created_at: '2026-10-13T10:30:00Z',
    ...overrides,
  }
}

function makeDetail(overrides?: Partial<AgentTraceDetail>): AgentTraceDetail {
  return {
    ...makeSummary(),
    steps: [
      {
        step_id: 'stp-c',
        seq: 2,
        kind: 'compile',
        name: 'compile_workflow',
        status: 'ok',
        duration_ms: 30,
        detail: { nodes: 2 },
      },
      {
        step_id: 'stp-a',
        seq: 0,
        kind: 'parse',
        name: 'structured_intent',
        status: 'ok',
        duration_ms: 12,
        detail: { lang: 'zh' },
      },
      {
        step_id: 'stp-b',
        seq: 1,
        kind: 'intent',
        name: 'build_intent',
        status: 'ok',
        duration_ms: 20,
        detail: { nodeCount: 2 },
      },
    ],
    module_diff_summary: null,
    token_usage: null,
    ...overrides,
  }
}

const listMock = listAgentTraces as unknown as ReturnType<typeof vi.fn>
const getMock = getAgentTrace as unknown as ReturnType<typeof vi.fn>

describe('AgentTracePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listMock.mockResolvedValue({ traces: [], total: 0 })
    getMock.mockResolvedValue(makeDetail())
  })

  // --- 列表 ---
  it('renders list from a mocked listAgentTraces response', async () => {
    listMock.mockResolvedValue({
      traces: [
        makeSummary({ trace_id: 'trc-1', kind: 'generate', status: 'ok' }),
        makeSummary({
          trace_id: 'trc-2',
          kind: 'modify',
          status: 'error',
          error_code: 'PATCH_FAILED',
          provider: 'anthropic',
          model: 'claude-sonnet',
          repair_count: 2,
          step_count: 5,
          duration_ms: 1200,
        }),
      ],
      total: 2,
    })

    render(<AgentTracePanel />)

    await waitFor(() => {
      expect(screen.getByLabelText('轨迹 trc-1')).toBeDefined()
      expect(screen.getByLabelText('轨迹 trc-2')).toBeDefined()
    })
    // kind labels also appear as filter <option>s; scope to the list rows
    const row1 = screen.getByLabelText('轨迹 trc-1')
    const row2 = screen.getByLabelText('轨迹 trc-2')
    expect(within(row1).getByText('generate')).toBeDefined()
    expect(within(row2).getByText('modify')).toBeDefined()
    expect(within(row1).getByText('ok')).toBeDefined()
    expect(within(row2).getByText('error')).toBeDefined()
    expect(screen.getByText(/openai\/gpt-4o/)).toBeDefined()
    expect(screen.getByText(/anthropic\/claude-sonnet/)).toBeDefined()
    expect(within(row1).getByText(/修复 1/)).toBeDefined()
    expect(within(row2).getByText(/5 步/)).toBeDefined()
    expect(listMock).toHaveBeenCalledWith({})
  })

  // --- 过滤 ---
  it('filters by kind re-issues the request with the right query param', async () => {
    render(<AgentTracePanel />)

    await waitFor(() => {
      expect(listMock).toHaveBeenCalledTimes(1)
    })

    fireEvent.change(screen.getByLabelText('类型'), { target: { value: 'modify' } })

    await waitFor(() => {
      expect(listMock).toHaveBeenLastCalledWith({ kind: 'modify' })
    })
  })

  it('filters by workflow_id re-issues the request with workflow_id param', async () => {
    render(<AgentTracePanel />)

    await waitFor(() => {
      expect(listMock).toHaveBeenCalledTimes(1)
    })

    fireEvent.change(screen.getByLabelText('工作流 ID'), { target: { value: 'wf-42' } })

    await waitFor(() => {
      expect(listMock).toHaveBeenLastCalledWith({ workflow_id: 'wf-42' })
    })
  })

  // --- 详情 / 步骤 ---
  it('selecting a row fetches detail and renders steps in seq order', async () => {
    listMock.mockResolvedValue({ traces: [makeSummary()], total: 1 })
    getMock.mockResolvedValue(makeDetail())

    render(<AgentTracePanel />)
    await waitFor(() => {
      expect(screen.getByLabelText('轨迹 trc-1')).toBeDefined()
    })

    fireEvent.click(screen.getByLabelText('轨迹 trc-1'))

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('trc-1')
    })
    await waitFor(() => {
      expect(screen.getByText('structured_intent')).toBeDefined()
    })

    // steps delivered out of order; DOM must be seq 0, 1, 2
    const timeline = screen.getByText('步骤时间线').closest('.exec-events') as HTMLElement
    const stepNames = within(timeline)
      .getAllByRole('button')
      .map((el) => el.textContent ?? '')
    const order = ['structured_intent', 'build_intent', 'compile_workflow'].map((name) =>
      stepNames.findIndex((t) => t.includes(name)),
    )
    expect(order).toEqual([0, 1, 2])
  })

  it('expands step detail on click and shows detail JSON', async () => {
    listMock.mockResolvedValue({ traces: [makeSummary()], total: 1 })
    render(<AgentTracePanel />)
    await waitFor(() => {
      expect(screen.getByLabelText('轨迹 trc-1')).toBeDefined()
    })

    fireEvent.click(screen.getByLabelText('轨迹 trc-1'))
    await waitFor(() => {
      expect(screen.getByText('structured_intent')).toBeDefined()
    })

    fireEvent.click(screen.getByText('structured_intent').closest('button')!)

    const detailEl = await screen.findByTestId('step-detail')
    expect(detailEl.textContent).toContain('lang')
    expect(detailEl.textContent).toContain('zh')
  })

  // --- module_diff_summary / token_usage ---
  it('renders module_diff_summary and token_usage when present', async () => {
    listMock.mockResolvedValue({ traces: [makeSummary()], total: 1 })
    getMock.mockResolvedValue(
      makeDetail({
        module_diff_summary: { added: 2, removed: 1, updated: 3, modules: [] },
        token_usage: { prompt_tokens: 100, completion_tokens: 50, total_tokens: 150 },
      }),
    )

    render(<AgentTracePanel />)
    await waitFor(() => {
      expect(screen.getByLabelText('轨迹 trc-1')).toBeDefined()
    })
    fireEvent.click(screen.getByLabelText('轨迹 trc-1'))

    await waitFor(() => {
      expect(screen.getByTestId('module-diff-summary')).toBeDefined()
      expect(screen.getByTestId('token-usage')).toBeDefined()
    })
    expect(screen.getByText('+2')).toBeDefined()
    expect(screen.getByText('-1')).toBeDefined()
    expect(screen.getByText('~3')).toBeDefined()
    expect(screen.getByText(/total 150/)).toBeDefined()
    expect(screen.getByText(/prompt 100/)).toBeDefined()
  })

  it('does not render module_diff_summary / token_usage sections when null', async () => {
    listMock.mockResolvedValue({ traces: [makeSummary()], total: 1 })
    getMock.mockResolvedValue(
      makeDetail({ module_diff_summary: null, token_usage: null }),
    )

    render(<AgentTracePanel />)
    await waitFor(() => {
      expect(screen.getByLabelText('轨迹 trc-1')).toBeDefined()
    })
    fireEvent.click(screen.getByLabelText('轨迹 trc-1'))

    await waitFor(() => {
      expect(screen.getByText('步骤时间线')).toBeDefined()
    })
    expect(screen.queryByTestId('module-diff-summary')).toBeNull()
    expect(screen.queryByTestId('token-usage')).toBeNull()
    expect(screen.queryByText('模块变更')).toBeNull()
    expect(screen.queryByText('Token 用量')).toBeNull()
  })

  // --- prompt_hash 截断 ---
  it('prompt_hash is truncated and never rendered as raw full 64-char text in the list', async () => {
    listMock.mockResolvedValue({ traces: [makeSummary()], total: 1 })

    const { container } = render(<AgentTracePanel />)
    await waitFor(() => {
      expect(screen.getByLabelText('轨迹 trc-1')).toBeDefined()
    })

    const text = container.textContent ?? ''
    expect(text).not.toContain(FULL_HASH)
    // first 12 chars + ellipsis
    expect(text).toContain('a1b2c3d4e5f6')
    expect(text).toContain('…')
    // labeled clearly as a hash (visible "hash" prefix + tooltip title)
    expect(screen.getAllByText(/hash /).length).toBeGreaterThan(0)
    expect(container.querySelector('[title*="哈希"]')).not.toBeNull()
  })

  it('prompt_hash stays truncated inside the detail view too', async () => {
    listMock.mockResolvedValue({ traces: [makeSummary()], total: 1 })
    const { container } = render(<AgentTracePanel />)
    await waitFor(() => {
      expect(screen.getByLabelText('轨迹 trc-1')).toBeDefined()
    })
    fireEvent.click(screen.getByLabelText('轨迹 trc-1'))
    await waitFor(() => {
      expect(screen.getByText('步骤时间线')).toBeDefined()
    })

    expect(container.textContent).not.toContain(FULL_HASH)
    expect(container.textContent).toContain('a1b2c3d4e5f6')
  })

  // --- 404 ---
  it('shows error state on TRACE_NOT_FOUND 404 when loading detail', async () => {
    listMock.mockResolvedValue({ traces: [makeSummary()], total: 1 })
    getMock.mockRejectedValue(
      new AgentTraceApiError('trace not found', 404, 'TRACE_NOT_FOUND'),
    )

    render(<AgentTracePanel />)
    await waitFor(() => {
      expect(screen.getByLabelText('轨迹 trc-1')).toBeDefined()
    })
    fireEvent.click(screen.getByLabelText('轨迹 trc-1'))

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('TRACE_NOT_FOUND')
    expect(alert.textContent).toContain('trace not found')
  })

  it('shows error state when the list request fails', async () => {
    listMock.mockRejectedValue(
      new AgentTraceApiError('list failed', 500, 'INTERNAL'),
    )

    render(<AgentTracePanel />)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('INTERNAL')
    expect(alert.textContent).toContain('list failed')
  })

  // --- 空态 ---
  it('renders empty state when the list is empty', async () => {
    listMock.mockResolvedValue({ traces: [], total: 0 })

    render(<AgentTracePanel />)

    await waitFor(() => {
      expect(screen.getByText('暂无轨迹记录')).toBeDefined()
    })
  })

  // --- 密钥兜底 ---
  it('does not re-expose an sk-... secret that arrives in step detail', async () => {
    const secret = 'sk-live-1234567890abcdef'
    listMock.mockResolvedValue({ traces: [makeSummary()], total: 1 })
    getMock.mockResolvedValue(
      makeDetail({
        steps: [
          {
            step_id: 'stp-sec',
            seq: 0,
            kind: 'tool',
            name: 'call_provider',
            status: 'ok',
            duration_ms: 5,
            detail: {
              api_key: secret,
              note: `using key ${secret}`,
              nested: { authorization: secret },
            },
          },
        ],
      }),
    )

    const { container } = render(<AgentTracePanel />)
    await waitFor(() => {
      expect(screen.getByLabelText('轨迹 trc-1')).toBeDefined()
    })
    fireEvent.click(screen.getByLabelText('轨迹 trc-1'))
    await waitFor(() => {
      expect(screen.getByText('call_provider')).toBeDefined()
    })

    // expand step detail so raw JSON would be visible if unmasked
    fireEvent.click(screen.getByText('call_provider').closest('button')!)
    await screen.findByTestId('step-detail')

    expect(container.textContent).not.toContain(secret)
    expect(container.textContent).toContain('[REDACTED]')
  })
})
