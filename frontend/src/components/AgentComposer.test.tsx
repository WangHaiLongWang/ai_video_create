/**
 * AgentComposer -- Agent v2 browser main chain tests
 *
 * Tests the complete flow: generate -> preview -> apply -> undo/run
 * Also tests: error handling, version conflict, modify mode, validation errors
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
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

/* ==================== MOD-R3-004: modify diff / module diff / destructive confirm ==================== */

const mockModifyPreview: api.AgentPreviewResponse_v2 = {
  intent: {
    name: 'Modified Workflow',
    nodes: [
      {
        alias: 'input',
        kind: 'textInput',
        moduleId: 'core.textInput',
        moduleVersion: '1.2.0',
        configOverrides: { prompt: 'hello' },
      },
      { alias: 'storyboard', kind: 'storyboard' },
    ],
    connections: [],
  },
  // Full rebuilt graph with brand-new ids — must NOT replace the canvas on modify apply
  compiled_workflow: {
    id: 'wf-compiled',
    name: 'Rebuilt',
    schemaVersion: '2.0',
    nodes: [
      {
        id: 'BRAND-NEW-ID',
        type: 'custom',
        position: { x: 0, y: 0 },
        data: { kind: 'textInput', label: 'Rebuilt', description: '', status: 'idle', config: {} },
      },
    ],
    edges: [],
  },
  validation_errors: [],
  repair_steps: [],
  cost_estimate: null,
  warnings: [],
  can_apply: true,
  patch: {
    description: '重配置分镜节点',
    add_nodes: [],
    remove_nodes: [],
    update_nodes: [{ id: 'n2', config: { scenes: 5 } }],
    add_edges: [],
    remove_edges: [],
  },
  diff: '~ n2 config.scenes: 3 -> 5',
  destructive: false,
  module_diffs: [
    {
      nodeId: 'n2',
      moduleId: 'core.storyboard',
      from: '1.0.0',
      to: '1.1.0',
      type: 'upgraded',
      details: {
        versionFrom: '1.0.0',
        versionTo: '1.1.0',
        breaking: false,
        addedFields: [{ key: 'style' }],
        removedFields: ['oldField'],
        changedFields: [{ field: 'scenes', changes: { default: { from: 3, to: 5 } } }],
        addedPorts: [],
        removedPorts: [],
        changedPorts: [],
      },
    },
    {
      nodeId: 'n1',
      moduleId: 'core.textInput',
      type: 'reconfigured',
      details: { changedKeys: ['prompt'], from: { prompt: 'a' }, to: { prompt: 'b' } },
    },
  ],
}

const mockDestructivePreview: api.AgentPreviewResponse_v2 = {
  intent: { name: 'Destructive', nodes: [], connections: [] },
  compiled_workflow: null,
  validation_errors: [],
  repair_steps: [],
  cost_estimate: null,
  warnings: [],
  can_apply: true,
  patch: {
    description: '删除输出节点',
    add_nodes: [],
    remove_nodes: ['n3'],
    update_nodes: [],
    add_edges: [],
    remove_edges: ['e2'],
  },
  diff: '- n3\n- e2',
  destructive: true,
}

/** Drive the modify flow: toggle mode -> instruction -> submit. */
function runModify(instruction: string) {
  fireEvent.click(screen.getByText('修改现有工作流'))
  fireEvent.change(screen.getByLabelText('修改指令'), { target: { value: instruction } })
  fireEvent.click(screen.getByText('修改'))
}

describe('AgentComposer modify diff (MOD-R3-004)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupStore()
    setupExecStore()
    if (typeof globalThis.structuredClone === 'undefined') {
      globalThis.structuredClone = (obj) => JSON.parse(JSON.stringify(obj))
    }
  })

  it('modify preview renders an incremental diff, not the full graph listing', async () => {
    vi.mocked(api.agentModifyPreview_v2).mockResolvedValue(mockModifyPreview)

    render(<AgentComposer />)
    runModify('把分镜改成 5 场')

    await waitFor(() => {
      expect(api.agentModifyPreview_v2).toHaveBeenCalledWith('wf-test-1', '把分镜改成 5 场')
      expect(screen.getByText('变更内容（增量 Diff）')).toBeDefined()
    })

    // Patch rows (修改不重建 evidence)
    expect(screen.getByText('修改节点')).toBeDefined()
    expect(screen.getByText('n2')).toBeDefined()
    expect(screen.getByText('配置 scenes')).toBeDefined()

    // Full graph listing is NOT the primary view for modify
    expect(screen.queryByText(/编译后工作流/)).toBeNull()

    // Human-readable diff text
    expect(screen.getByText('差异文本')).toBeDefined()
    expect(screen.getByText('~ n2 config.scenes: 3 -> 5')).toBeDefined()
  })

  it('module/version/config changes are visible in the preview', async () => {
    vi.mocked(api.agentModifyPreview_v2).mockResolvedValue(mockModifyPreview)

    render(<AgentComposer />)
    runModify('升级分镜模块')

    await waitFor(() => {
      expect(screen.getByText('模块变更')).toBeDefined()
    })

    // type badges
    expect(screen.getByText('升级')).toBeDefined()
    expect(screen.getByText('配置变更')).toBeDefined()

    // moduleId + versions
    expect(screen.getByText('core.storyboard')).toBeDefined()
    expect(screen.getByText('1.0.0 → 1.1.0')).toBeDefined()

    // upgraded field/port deltas from details
    expect(screen.getByText('style')).toBeDefined()    // addedFields
    expect(screen.getByText('oldField')).toBeDefined() // removedFields
    expect(screen.getByText('scenes')).toBeDefined()   // changedFields

    // reconfigured changed keys
    expect(screen.getByText('配置键 prompt')).toBeDefined()

    // NodeIntent module fields surfaced in the intent preview
    expect(screen.getByText('core.textInput@1.2.0')).toBeDefined()
    expect(screen.getByText('覆盖 prompt')).toBeDefined()
  })

  it('destructive op shows a confirmation with removals and can be aborted', async () => {
    vi.mocked(api.agentModifyPreview_v2).mockResolvedValue(mockDestructivePreview)

    render(<AgentComposer />)
    runModify('删掉输出节点')

    await waitFor(() => {
      expect(screen.getByText('变更内容（增量 Diff）')).toBeDefined()
    })

    // Destructive banner (distinct from the validation banner)
    expect(screen.getByText('此操作包含删除（破坏性变更），应用前需二次确认')).toBeDefined()
    expect(screen.getByText('将删除节点')).toBeDefined()
    expect(screen.getByText('将删除连线')).toBeDefined()
    // Validation banner must NOT appear (can_apply is true)
    expect(screen.queryByText('此操作存在验证问题，无法安全应用')).toBeNull()

    // First click opens the confirmation, does not apply
    fireEvent.click(screen.getByText('确认应用'))
    await waitFor(() => {
      expect(screen.getByText('确认删除以下内容并应用？')).toBeDefined()
    })
    const dialog = within(screen.getByRole('alertdialog', { name: '确认破坏性操作' }))
    expect(dialog.getByText('删除节点')).toBeDefined()
    expect(dialog.getByText('n3')).toBeDefined()
    expect(dialog.getByText('删除连线')).toBeDefined()
    expect(dialog.getByText('e2')).toBeDefined()
    expect(api.agentApply_v2).not.toHaveBeenCalled()

    // Abort: confirmation closes, nothing applied
    fireEvent.click(screen.getByText('取消'))
    await waitFor(() => {
      expect(screen.queryByText('确认删除以下内容并应用？')).toBeNull()
      expect(screen.getByText('确认应用')).toBeDefined()
    })
    expect(api.agentApply_v2).not.toHaveBeenCalled()
  })

  it('destructive op applies only after explicit confirmation', async () => {
    vi.mocked(api.agentModifyPreview_v2).mockResolvedValue(mockDestructivePreview)
    vi.mocked(api.agentApply_v2).mockResolvedValue({ success: true, workflow_id: 'wf-test-1', version: 2 })

    render(<AgentComposer />)
    runModify('删掉输出节点')

    await waitFor(() => {
      expect(screen.getByText('确认应用')).toBeDefined()
    })

    fireEvent.click(screen.getByText('确认应用'))
    await waitFor(() => {
      expect(screen.getByText('确认删除并应用')).toBeDefined()
    })

    fireEvent.click(screen.getByText('确认删除并应用'))
    await waitFor(() => {
      expect(api.agentApply_v2).toHaveBeenCalledWith(
        mockDestructivePreview.intent,
        { workflowId: 'wf-test-1', expectedVersion: 1 },
      )
    })
  })

  it('apply-as-patch preserves untouched node ids in the store (no rebuild)', async () => {
    const workflowWithNodes: api.WorkflowSpec = {
      id: 'wf-test-1',
      name: 'Test Workflow',
      schemaVersion: '2.0',
      nodes: [
        {
          id: 'keep-a', type: 'custom', position: { x: 0, y: 0 },
          data: { kind: 'textInput', label: 'A', description: '', status: 'idle', config: {} },
        },
        {
          id: 'keep-b', type: 'custom', position: { x: 100, y: 0 },
          data: { kind: 'storyboard', label: 'B', description: '', status: 'idle', config: { scenes: 3 } },
        },
        {
          id: 'drop-c', type: 'custom', position: { x: 200, y: 0 },
          data: { kind: 'output', label: 'C', description: '', status: 'idle', config: {} },
        },
      ],
      edges: [
        { id: 'e-ab', source: 'keep-a', target: 'keep-b' },
        { id: 'e-bc', source: 'keep-b', target: 'drop-c' },
      ],
    }
    setupStore({ workflow: workflowWithNodes })

    const patchPreview: api.AgentPreviewResponse_v2 = {
      ...mockDestructivePreview,
      intent: { name: 'Drop output', nodes: [], connections: [] },
      patch: {
        description: '删除输出节点并调整分镜',
        add_nodes: [],
        remove_nodes: ['drop-c'],
        update_nodes: [{ id: 'keep-b', config: { scenes: 5 } }],
        add_edges: [],
        remove_edges: [],
      },
      // rebuilt spec with brand-new ids must be ignored on modify apply
      compiled_workflow: {
        id: 'wf-compiled',
        name: 'Rebuilt',
        schemaVersion: '2.0',
        nodes: [
          {
            id: 'BRAND-NEW-ID', type: 'custom', position: { x: 0, y: 0 },
            data: { kind: 'textInput', label: 'Rebuilt', description: '', status: 'idle', config: {} },
          },
        ],
        edges: [],
      },
    }
    vi.mocked(api.agentModifyPreview_v2).mockResolvedValue(patchPreview)
    vi.mocked(api.agentApply_v2).mockResolvedValue({ success: true, workflow_id: 'wf-test-1', version: 2 })

    render(<AgentComposer />)
    runModify('删除输出节点')

    await waitFor(() => {
      expect(screen.getByText('确认应用')).toBeDefined()
    })

    // destructive -> two-step confirm
    fireEvent.click(screen.getByText('确认应用'))
    await waitFor(() => {
      expect(screen.getByText('确认删除并应用')).toBeDefined()
    })
    fireEvent.click(screen.getByText('确认删除并应用'))

    await waitFor(() => {
      expect(mockSetWorkflow).toHaveBeenCalled()
    })

    // Store state written by setWorkflow: untouched ids preserved, removals applied
    const applied = mockSetWorkflow.mock.calls[0][0] as typeof workflowWithNodes
    const nodeIds = applied.nodes.map((n) => n.id)
    expect(nodeIds).toContain('keep-a')
    expect(nodeIds).toContain('keep-b')
    expect(nodeIds).not.toContain('drop-c')
    // NOT a full rebuild from compiled_workflow
    expect(nodeIds).not.toContain('BRAND-NEW-ID')

    // update_nodes label/config applied
    const keepB = applied.nodes.find((n) => n.id === 'keep-b')
    expect(keepB?.data.config).toEqual({ scenes: 5 })
    expect(keepB?.data.label).toBe('B') // untouched fields preserved

    // edge to removed node dropped; other edge id preserved
    expect(applied.edges.map((e) => e.id)).toEqual(['e-ab'])
  })

  it('generate still does a full replace (not patch)', async () => {
    const generatePreview: api.AgentPreviewResponse_v2 = {
      ...mockPreviewResponse,
      patch: null,
      compiled_workflow: {
        id: 'wf-generated',
        name: 'Generated',
        schemaVersion: '2.0',
        nodes: [
          {
            id: 'gen-1', type: 'custom', position: { x: 0, y: 0 },
            data: { kind: 'textInput', label: 'Gen', description: '', status: 'idle', config: {} },
          },
        ],
        edges: [],
      },
    }
    vi.mocked(api.agentGeneratePreview_v2).mockResolvedValue(generatePreview)
    vi.mocked(api.agentApply_v2).mockResolvedValue({ success: true, workflow_id: 'wf-generated', version: 2 })

    render(<AgentComposer />)

    fireEvent.click(screen.getByText('生成'))
    await waitFor(() => {
      expect(screen.getByText('确认应用')).toBeDefined()
    })
    // Generate shows the full graph listing, not a patch diff
    expect(screen.getByText(/编译后工作流/)).toBeDefined()
    expect(screen.queryByText('变更内容（增量 Diff）')).toBeNull()

    fireEvent.click(screen.getByText('确认应用'))
    await waitFor(() => {
      expect(mockSetWorkflow).toHaveBeenCalledWith(generatePreview.compiled_workflow)
    })
  })
})
