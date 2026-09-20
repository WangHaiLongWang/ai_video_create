import { describe, expect, it, vi, beforeEach } from 'vitest'
import { createPromptToVideoWorkflow } from './workflow'

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value }),
    removeItem: vi.fn((key: string) => { delete store[key] }),
    clear: vi.fn(() => { store = {} }),
    get length() { return Object.keys(store).length },
    key: vi.fn((_i: number) => null),
  }
})()
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock })

// Mock fetch
globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve([]) })

// Import store after mocks are set up
const { useStudioStore } = await import('./store')

describe('store undo/redo', () => {
  beforeEach(() => {
    localStorageMock.clear()
    const wf = createPromptToVideoWorkflow()
    useStudioStore.setState({
      workflow: wf,
      past: [],
      future: [],
      selectedNodeId: null,
      isDirty: false,
      serverVersion: null,
    })
  })

  it('undo reverts to previous workflow', () => {
    const { setWorkflow, undo } = useStudioStore.getState()
    const wf = createPromptToVideoWorkflow('新主题')
    setWorkflow(wf)
    expect(useStudioStore.getState().workflow.nodes[0].data.config.prompt).toBe('新主题')
    undo()
    expect(useStudioStore.getState().workflow.nodes[0].data.config.prompt).toBe('雨夜，一名送信人在未来城市穿行')
  })

  it('redo restores undone workflow', () => {
    const { setWorkflow, undo, redo } = useStudioStore.getState()
    const wf = createPromptToVideoWorkflow(' redo 测试')
    setWorkflow(wf)
    undo()
    expect(useStudioStore.getState().future.length).toBe(1)
    redo()
    expect(useStudioStore.getState().workflow.nodes[0].data.config.prompt).toBe(' redo 测试')
  })

  it('canUndo returns true after a change', () => {
    const { setWorkflow } = useStudioStore.getState()
    setWorkflow(createPromptToVideoWorkflow('test'))
    expect(useStudioStore.getState().canUndo()).toBe(true)
  })

  it('canRedo returns false initially', () => {
    expect(useStudioStore.getState().canRedo()).toBe(false)
  })

  it('new change clears redo stack', () => {
    const { setWorkflow, undo } = useStudioStore.getState()
    setWorkflow(createPromptToVideoWorkflow('first'))
    undo()
    expect(useStudioStore.getState().future.length).toBe(1)
    setWorkflow(createPromptToVideoWorkflow('second'))
    expect(useStudioStore.getState().future.length).toBe(0)
  })
})

describe('store node operations', () => {
  beforeEach(() => {
    localStorageMock.clear()
    const wf = createPromptToVideoWorkflow()
    useStudioStore.setState({
      workflow: wf,
      past: [],
      future: [],
      selectedNodeId: null,
      isDirty: false,
    })
  })

  it('updateConfig modifies selected node config', () => {
    const { selectNode, updateConfig } = useStudioStore.getState()
    const nodeId = useStudioStore.getState().workflow.nodes[0].id
    selectNode(nodeId)
    updateConfig('prompt', '新提示词')
    const node = useStudioStore.getState().workflow.nodes.find((n) => n.id === nodeId)
    expect(node?.data.config.prompt).toBe('新提示词')
  })

  it('selectNode sets selectedNodeId', () => {
    const { selectNode } = useStudioStore.getState()
    selectNode('some-id')
    expect(useStudioStore.getState().selectedNodeId).toBe('some-id')
  })

  it('selectNode(null) clears selection', () => {
    const { selectNode } = useStudioStore.getState()
    selectNode('some-id')
    selectNode(null)
    expect(useStudioStore.getState().selectedNodeId).toBeNull()
  })
})

describe('field rename config key migration', () => {
  const nodeId = 'test-node'
  const field: import('./types').FieldDefinition = { id: 'camera_motion', label: 'Camera Motion', type: 'text' }

  beforeEach(() => {
    localStorageMock.clear()
    useStudioStore.setState({
      workflow: {
        id: 'wf',
        name: 'Test',
        schemaVersion: '2.0',
        nodes: [{
          id: nodeId,
          type: 'studio',
          position: { x: 0, y: 0 },
          data: {
            label: 'Node',
            description: '',
            kind: 'textInput',
            status: 'idle',
            config: { camera_motion: 'slow_push', other_key: 'keep' },
            fieldSchema: [field],
          },
        }],
        edges: [],
      },
      past: [],
      future: [],
      selectedNodeId: null,
      isDirty: false,
    })
  })

  it('migrates config key when field ID is renamed', () => {
    const { updateField } = useStudioStore.getState()
    const renamed: import('./types').FieldDefinition = { ...field, id: 'camera_move', label: 'Camera Move' }
    updateField(nodeId, 'camera_motion', renamed)

    const node = useStudioStore.getState().workflow.nodes.find((n) => n.id === nodeId)!
    expect(node.data.config).toEqual({ camera_move: 'slow_push', other_key: 'keep' })
    expect(node.data.fieldSchema).toHaveLength(1)
    expect(node.data.fieldSchema![0].id).toBe('camera_move')
  })

  it('preserves other config keys during rename', () => {
    const { updateField } = useStudioStore.getState()
    const renamed: import('./types').FieldDefinition = { ...field, id: 'camera_move' }
    updateField(nodeId, 'camera_motion', renamed)

    const node = useStudioStore.getState().workflow.nodes.find((n) => n.id === nodeId)!
    expect(node.data.config.other_key).toBe('keep')
  })

  it('undo rename restores original config key', () => {
    const { updateField, undo } = useStudioStore.getState()
    const renamed: import('./types').FieldDefinition = { ...field, id: 'camera_move' }
    updateField(nodeId, 'camera_motion', renamed)

    // Verify rename happened
    const renamedNode = useStudioStore.getState().workflow.nodes.find((n) => n.id === nodeId)!
    expect(renamedNode.data.config.camera_move).toBe('slow_push')

    undo()

    const restoredNode = useStudioStore.getState().workflow.nodes.find((n) => n.id === nodeId)!
    expect(restoredNode.data.config.camera_motion).toBe('slow_push')
    expect(restoredNode.data.config.camera_move).toBeUndefined()
  })
})

describe('field deletion config cleanup', () => {
  const nodeId = 'test-node-del'

  beforeEach(() => {
    localStorageMock.clear()
    useStudioStore.setState({
      workflow: {
        id: 'wf',
        name: 'Test',
        schemaVersion: '2.0',
        nodes: [{
          id: nodeId,
          type: 'studio',
          position: { x: 0, y: 0 },
          data: {
            label: 'Node',
            description: '',
            kind: 'textInput',
            status: 'idle',
            config: { my_field: 'to_delete', other: 'kept' },
            fieldSchema: [
              { id: 'my_field', label: 'My Field', type: 'text' },
            ],
          },
        }],
        edges: [],
      },
      past: [],
      future: [],
      selectedNodeId: null,
      isDirty: false,
    })
  })

  it('removes config value when field is deleted', () => {
    const { deleteField } = useStudioStore.getState()
    deleteField(nodeId, 'my_field')

    const node = useStudioStore.getState().workflow.nodes.find((n) => n.id === nodeId)!
    expect(node.data.config.my_field).toBeUndefined()
    expect(node.data.config.other).toBe('kept')
    expect(node.data.fieldSchema).toHaveLength(0)
  })

  it('undo delete restores config value', () => {
    const { deleteField, undo } = useStudioStore.getState()
    deleteField(nodeId, 'my_field')

    undo()

    const node = useStudioStore.getState().workflow.nodes.find((n) => n.id === nodeId)!
    expect(node.data.config.my_field).toBe('to_delete')
    expect(node.data.fieldSchema).toHaveLength(1)
    expect(node.data.fieldSchema![0].id).toBe('my_field')
  })
})
