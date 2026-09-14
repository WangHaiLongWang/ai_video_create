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
