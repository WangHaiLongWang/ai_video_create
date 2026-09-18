/**
 * AgentComposer -- Agent v2 browser main chain tests
 *
 * Tests the complete flow: generate -> preview -> apply -> undo/run
 * Also tests: error handling, version conflict, modify mode, validation errors
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AgentComposer } from './AgentComposer'
import * as api from '../api'
import * as store from '../store'
import * as executionStore from '../stores/executionStore'

vi.mock('../api')
vi.mock('../store')
vi.mock('../stores/executionStore')

const mockSetWorkflow = vi.fn()
const mockStartExecution = vi.fn()

const mockWorkflow = {
  id: 'wf-test-1',
  name: 'Test Workflow',
  schemaVersion: '2.0' as const,
  nodes: [],
  edges: [],
}

function setupStore(overrides?: Partial<ReturnType<typeof store.useStudioStore.getState>>) {
  vi.mocked(store.useStudioStore).mockReturnValue({
    workflow: mockWorkflow,
    setWorkflow: mockSetWorkflow,
    serverVersion: 1,
    ...overrides,
  } as ReturnType<typeof store.useStudioStore.getState>)
}

function setupExecStore(overrides?: Partial<ReturnType<typeof executionStore.useExecutionStore.getState>>) {
  vi.mocked(executionStore.useExecutionStore).mockReturnValue({
    startExecution: mockStartExecution,
    status: 'idle',
    ...overrides,
  } as ReturnType<typeof executionStore.useExecutionStore.getState>)
}

const mockPreviewResponse: api.AgentPreviewResponse_v2 = {
  intent: {
    name: 'Test Workflow',
    nodes: [
      { alias: 'input', kind: 'textInput', config: { prompt: 'test' } },
      { alias: 'storyboard', kind: 'storyboard', config: { scenes: 3 } },
    ],
    connections: [
      { source: { node: 'input', port: 'text' }, target: { node: 'storyboard', port: 'prompt' }, mode: 'direct' },
    ],
    scene_count: 3,
  },
  compiled_workflow: {
    id: 'wf-compiled',
    name: 'Test Workflow',
    schemaVersion: '2.0',
    nodes: [
      { id: 'n1', type: 'custom', position: { x: 0, y: 0 }, data: { kind: 'textInput', label: 'Input', description: '', status: 'idle', config: {} } },
    ],
    edges: [],
  },
  validation_errors: [],
  repair_steps: [],
  cost_estimate: {
    scene_count: 3,
    variant_count: 1,
    image_calls: 3,
    video_calls: 3,
    storyboard_calls: 1,
    concat_calls: 1,
    total_calls: 8,
    estimated_duration_seconds: 120,
  },
  warnings: [],
  can_apply: true,
}

describe('AgentComposer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupStore()
    setupExecStore()
    // Mock structuredClone for undo snapshots
    if (typeof globalThis.structuredClone === 'undefined') {
      globalThis.structuredClone = (obj) => JSON.parse(JSON.stringify(obj))
    }
  })

  it('renders the agent panel with prompt textarea and generate button', () => {
    render(<AgentComposer />)

    expect(screen.getByLabelText('描述想要创建的工作流')).toBeDefined()
    expect(screen.getByText('生成')).toBeDefined()
  })

  it('calls generate-preview-v2 when generate is clicked', async () => {
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(mockPreviewResponse)

    render(<AgentComposer />)

    const textarea = screen.getByLabelText('描述想要创建的工作流')
    fireEvent.change(textarea, { target: { value: '创建测试视频' } })
    fireEvent.click(screen.getByText('生成'))

    await waitFor(() => {
      expect(api.agentGeneratePreview_v2).toHaveBeenCalledWith('创建测试视频')
    })
  })

  it('shows preview with intent structure after successful generate', async () => {
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(mockPreviewResponse)

    render(<AgentComposer />)

    fireEvent.click(screen.getByText('生成'))

    await waitFor(() => {
      expect(screen.getByText('工作流结构')).toBeDefined()
      // Check unique aliases are shown
      expect(screen.getByText('input')).toBeDefined()
      expect(screen.getByText('storyboard')).toBeDefined()
    })
  })

  it('shows cost estimate in preview', async () => {
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(mockPreviewResponse)

    render(<AgentComposer />)

    fireEvent.click(screen.getByText('生成'))

    await waitFor(() => {
      expect(screen.getByText('调用预估')).toBeDefined()
    })
  })

  it('shows confirmation button with correct label', async () => {
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(mockPreviewResponse)

    render(<AgentComposer />)

    fireEvent.click(screen.getByText('生成'))

    await waitFor(() => {
      expect(screen.getByText('确认应用')).toBeDefined()
    })
  })

  it('applies preview with compiled_workflow on confirm', async () => {
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(mockPreviewResponse)
    vi.mocked(api.agentApply_v2).mockResolvedValue({ success: true, workflow_id: 'wf-compiled', version: 2 })

    render(<AgentComposer />)

    // Generate
    fireEvent.click(screen.getByText('生成'))
    await waitFor(() => {
      expect(screen.getByText('确认应用')).toBeDefined()
    })

    // Apply
    fireEvent.click(screen.getByText('确认应用'))

    await waitFor(() => {
      expect(api.agentApply_v2).toHaveBeenCalledWith(
        mockPreviewResponse.intent,
        { workflowId: 'wf-test-1', expectedVersion: 1 },
      )
      expect(mockSetWorkflow).toHaveBeenCalledWith(mockPreviewResponse.compiled_workflow)
    })
  })

  it('shows success banner with undo and run buttons after apply', async () => {
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(mockPreviewResponse)
    vi.mocked(api.agentApply_v2).mockResolvedValue({ success: true, workflow_id: 'wf-compiled', version: 2 })

    render(<AgentComposer />)

    // Generate + Apply
    fireEvent.click(screen.getByText('生成'))
    await waitFor(() => { expect(screen.getByText('确认应用')).toBeDefined() })

    fireEvent.click(screen.getByText('确认应用'))
    await waitFor(() => {
      expect(screen.getByText('已应用')).toBeDefined()
      expect(screen.getByText('撤销')).toBeDefined()
      expect(screen.getByText('运行')).toBeDefined()
    })
  })

  it('undo restores previous workflow state', async () => {
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(mockPreviewResponse)
    vi.mocked(api.agentApply_v2).mockResolvedValue({ success: true, workflow_id: 'wf-compiled', version: 2 })

    render(<AgentComposer />)

    // Generate + Apply
    fireEvent.click(screen.getByText('生成'))
    await waitFor(() => { expect(screen.getByText('确认应用')).toBeDefined() })

    fireEvent.click(screen.getByText('确认应用'))
    await waitFor(() => { expect(screen.getByText('已应用')).toBeDefined() })

    // Undo
    fireEvent.click(screen.getByText('撤销'))

    await waitFor(() => {
      expect(mockSetWorkflow).toHaveBeenCalledWith(mockWorkflow) // original workflow
    })
  })

  it('run button calls startExecution', async () => {
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(mockPreviewResponse)
    vi.mocked(api.agentApply_v2).mockResolvedValue({ success: true, workflow_id: 'wf-compiled', version: 2 })

    render(<AgentComposer />)

    // Generate + Apply
    fireEvent.click(screen.getByText('生成'))
    await waitFor(() => { expect(screen.getByText('确认应用')).toBeDefined() })

    fireEvent.click(screen.getByText('确认应用'))
    await waitFor(() => { expect(screen.getByText('运行')).toBeDefined() })

    // Run
    fireEvent.click(screen.getByText('运行'))

    await waitFor(() => {
      expect(mockStartExecution).toHaveBeenCalledWith('wf-test-1')
    })
  })

  it('shows version conflict error message on 409', async () => {
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(mockPreviewResponse)
    vi.mocked(api.agentApply_v2).mockResolvedValue({ success: false, error: '409 version conflict' })

    render(<AgentComposer />)

    // Generate + Apply
    fireEvent.click(screen.getByText('生成'))
    await waitFor(() => { expect(screen.getByText('确认应用')).toBeDefined() })

    fireEvent.click(screen.getByText('确认应用'))
    await waitFor(() => {
      expect(screen.getByText('工作流已被更新，请刷新后重试')).toBeDefined()
    })
  })

  it('shows validation errors in preview when can_apply is false', async () => {
    const errorResponse: api.AgentPreviewResponse_v2 = {
      ...mockPreviewResponse,
      can_apply: false,
      validation_errors: [
        { code: 'MISSING_INPUT', message: '节点缺少输入' },
      ],
    }
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(errorResponse)

    render(<AgentComposer />)

    fireEvent.click(screen.getByText('生成'))

    await waitFor(() => {
      expect(screen.getByText('MISSING_INPUT')).toBeDefined()
      expect(screen.getByText('节点缺少输入')).toBeDefined()
      expect(screen.getByText('无法应用')).toBeDefined()
    })
  })

  it('cancel clears preview', async () => {
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(mockPreviewResponse)

    render(<AgentComposer />)

    // Generate
    fireEvent.click(screen.getByText('生成'))
    await waitFor(() => { expect(screen.getByText('确认应用')).toBeDefined() })

    // Cancel
    fireEvent.click(screen.getByText('取消'))

    await waitFor(() => {
      expect(screen.queryByText('确认应用')).toBeNull()
    })
  })

  it('shows error when generate fails', async () => {
    vi.mocked(api.agentGeneratePreview_v2).mockRejectedValue(new Error('网络错误'))

    render(<AgentComposer />)

    fireEvent.click(screen.getByText('生成'))

    await waitFor(() => {
      expect(screen.getByText('网络错误')).toBeDefined()
    })
  })

  it('disables apply button while applying', async () => {
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(mockPreviewResponse)
    // Make apply hang
    vi.mocked(api.agentApply_v2).mockReturnValue(new Promise(() => {}))

    render(<AgentComposer />)

    // Generate
    fireEvent.click(screen.getByText('生成'))
    await waitFor(() => { expect(screen.getByText('确认应用')).toBeDefined() })

    // Apply (will hang)
    fireEvent.click(screen.getByText('确认应用'))

    await waitFor(() => {
      const applyBtn = screen.getByText('应用中...')
      expect(applyBtn).toBeDefined()
      expect(applyBtn.closest('button')?.disabled).toBe(true)
    })
  })

  it('shows warnings in preview', async () => {
    const responseWithWarnings: api.AgentPreviewResponse_v2 = {
      ...mockPreviewResponse,
      warnings: ['场景数较多，预计执行时间较长'],
    }
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(responseWithWarnings)

    render(<AgentComposer />)

    fireEvent.click(screen.getByText('生成'))

    await waitFor(() => {
      expect(screen.getByText('场景数较多，预计执行时间较长')).toBeDefined()
    })
  })

  it('shows repair steps when present', async () => {
    const responseWithRepairs: api.AgentPreviewResponse_v2 = {
      ...mockPreviewResponse,
      repair_steps: [
        { attempt: 1, repairs_applied: ['MISSING_KIND'], errors_before: [], errors_after: [] },
      ],
    }
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(responseWithRepairs)

    render(<AgentComposer />)

    fireEvent.click(screen.getByText('生成'))

    await waitFor(() => {
      expect(screen.getByText('自动修复')).toBeDefined()
      expect(screen.getByText('#1')).toBeDefined()
      expect(screen.getByText('MISSING_KIND')).toBeDefined()
    })
  })

  it('can toggle modify mode', async () => {
    render(<AgentComposer />)

    fireEvent.click(screen.getByText('修改现有工作流'))

    await waitFor(() => {
      expect(screen.getByLabelText('修改指令')).toBeDefined()
      expect(screen.getByText('修改')).toBeDefined()
    })
  })
})
