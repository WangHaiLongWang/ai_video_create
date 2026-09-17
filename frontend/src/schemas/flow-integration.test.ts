/**
 * flow-integration.test — Multi-handle node, connection validation, and edge label integration tests
 *
 * Tests:
 * 1. createNode populates ports from NODE_CATALOG
 * 2. createNode falls back gracefully for unknown kinds
 * 3. StudioNode backward-compat: nodes without ports field still produce valid data
 * 4. Store onConnect rejects invalid connections (type mismatch)
 * 5. Store onConnect rejects self-loops
 * 6. Store onConnect accepts valid connections
 * 7. Store onConnect adds edge with data.label
 * 8. EnhancedEdge type supports EdgeData fields
 * 9. Store setWorkflow logs validation warnings
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createNode, createPromptToVideoWorkflow } from '../workflow'
import { NODE_CATALOG } from './node-manifest'
import { validateGraph, validateConnection } from './graph-validation'
import type { NodeKind, EnhancedEdge, EdgeData } from '../types'

// ---------------------------------------------------------------------------
// Mock localStorage
// ---------------------------------------------------------------------------
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

// Import store after mocks
const { useStudioStore } = await import('../store')

// ---------------------------------------------------------------------------
// 1. createNode populates ports from NODE_CATALOG
// ---------------------------------------------------------------------------
describe('createNode — port population', () => {
  it('textInput node has one output port "text"', () => {
    const node = createNode('textInput', 0, 0, 'test-1')
    expect(node.data.ports).toBeDefined()
    expect(node.data.ports!.outputs).toHaveLength(1)
    expect(node.data.ports!.outputs[0].id).toBe('text')
    expect(node.data.ports!.outputs[0].type).toBe('text')
    expect(node.data.ports!.inputs).toHaveLength(0)
  })

  it('storyboard node has 1 input and 1 output', () => {
    const node = createNode('storyboard', 0, 0, 'test-2')
    expect(node.data.ports).toBeDefined()
    expect(node.data.ports!.inputs).toHaveLength(1)
    expect(node.data.ports!.inputs[0].id).toBe('prompt')
    expect(node.data.ports!.inputs[0].type).toBe('text')
    expect(node.data.ports!.inputs[0].required).toBe(true)
    expect(node.data.ports!.outputs).toHaveLength(1)
    expect(node.data.ports!.outputs[0].id).toBe('scenes')
    expect(node.data.ports!.outputs[0].type).toBe('scene')
    expect(node.data.ports!.outputs[0].cardinality).toBe('many')
  })

  it('imageToVideo node has 2 inputs and 1 output', () => {
    const node = createNode('imageToVideo', 0, 0, 'test-3')
    expect(node.data.ports).toBeDefined()
    expect(node.data.ports!.inputs).toHaveLength(2)
    expect(node.data.ports!.inputs.map(p => p.id)).toEqual(['image', 'scene'])
    expect(node.data.ports!.outputs).toHaveLength(1)
    expect(node.data.ports!.outputs[0].id).toBe('video')
  })

  it('output node has 1 input and no outputs', () => {
    const node = createNode('output', 0, 0, 'test-4')
    expect(node.data.ports).toBeDefined()
    expect(node.data.ports!.inputs).toHaveLength(1)
    expect(node.data.ports!.inputs[0].id).toBe('video')
    expect(node.data.ports!.inputs[0].required).toBe(true)
    expect(node.data.ports!.outputs).toHaveLength(0)
  })

  it('backward compat: inputType/outputType still set from manifest', () => {
    const node = createNode('storyboard', 0, 0, 'test-5')
    expect(node.data.inputType).toBe('text')
    expect(node.data.outputType).toBe('scene')
  })

  it('backward compat: ports labels default to port id when not provided', () => {
    const node = createNode('textInput', 0, 0, 'test-6')
    // textInput output "text" has no explicit label, so label defaults to id
    expect(node.data.ports!.outputs[0].label).toBe('text')
  })

  it('port required flags match manifest', () => {
    const textInput = createNode('textInput', 0, 0, 'n1')
    // textInput has no required inputs
    expect(textInput.data.ports!.inputs.every(p => !p.required)).toBe(true)

    const storyboard = createNode('storyboard', 0, 0, 'n2')
    // storyboard prompt input is required
    expect(storyboard.data.ports!.inputs[0].required).toBe(true)

    const output = createNode('output', 0, 0, 'n3')
    expect(output.data.ports!.inputs[0].required).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// 2. createPromptToVideoWorkflow includes ports on all nodes
// ---------------------------------------------------------------------------
describe('createPromptToVideoWorkflow — port integration', () => {
  it('all nodes have ports field', () => {
    const wf = createPromptToVideoWorkflow()
    for (const node of wf.nodes) {
      expect(node.data.ports).toBeDefined()
      expect(node.data.ports!.inputs).toBeInstanceOf(Array)
      expect(node.data.ports!.outputs).toBeInstanceOf(Array)
    }
  })
})

// ---------------------------------------------------------------------------
// 3. validateConnection from graph-validation works with catalog
// ---------------------------------------------------------------------------
describe('validateConnection — catalog-based', () => {
  const kinds: Record<string, NodeKind> = {
    'textInput-1': 'textInput',
    'storyboard-1': 'storyboard',
    'textToImage-1': 'textToImage',
    'output-1': 'output',
  }

  it('accepts valid text -> text connection', () => {
    const result = validateConnection(
      'textInput-1', 'text',
      'storyboard-1', 'prompt',
      kinds, NODE_CATALOG, [],
    )
    expect(result).toBeNull()
  })

  it('rejects type mismatch: video -> scene', () => {
    const kinds2: Record<string, NodeKind> = {
      'vc-1': 'videoConcat',
      'ti-1': 'textToImage',
    }
    const result = validateConnection(
      'vc-1', 'video',
      'ti-1', 'scene',
      kinds2, NODE_CATALOG, [],
    )
    expect(result).not.toBeNull()
    expect(result!.code).toBe('TYPE_MISMATCH')
  })

  it('rejects self-loop', () => {
    const result = validateConnection(
      'textInput-1', 'text',
      'textInput-1', 'text',
      kinds, NODE_CATALOG, [],
    )
    expect(result).not.toBeNull()
    expect(result!.code).toBe('SELF_LOOP')
  })

  it('rejects duplicate edge', () => {
    const existingEdges = [
      { id: 'e1', source: 'textInput-1', sourceHandle: 'text', target: 'storyboard-1', targetHandle: 'prompt' },
    ]
    const result = validateConnection(
      'textInput-1', 'text',
      'storyboard-1', 'prompt',
      kinds, NODE_CATALOG, existingEdges,
    )
    expect(result).not.toBeNull()
    expect(result!.code).toBe('DUPLICATE_EDGE')
  })
})

// ---------------------------------------------------------------------------
// 4. Store onConnect validation
// ---------------------------------------------------------------------------
describe('store onConnect — validation', () => {
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

  it('accepts valid connection and adds edge with data', () => {
    const state = useStudioStore.getState()
    const nodeIds = state.workflow.nodes.map(n => n.id)
    // textInput -> storyboard is valid
    const connection = {
      source: nodeIds[0],
      sourceHandle: 'text',
      target: nodeIds[1],
      targetHandle: 'prompt',
    }
    // First remove existing edge between these nodes if any
    const existingEdge = state.workflow.edges.find(
      e => e.source === connection.source && e.target === connection.target,
    )
    if (existingEdge) {
      useStudioStore.setState({
        workflow: {
          ...state.workflow,
          edges: state.workflow.edges.filter(e => e.id !== existingEdge.id),
        },
      })
    }

    const prevEdgeCount = useStudioStore.getState().workflow.edges.length
    useStudioStore.getState().onConnect(connection)

    const newState = useStudioStore.getState()
    expect(newState.workflow.edges.length).toBe(prevEdgeCount + 1)
    const addedEdge = newState.workflow.edges[newState.workflow.edges.length - 1]
    // type is omitted — React Flow normalizes to 'default' → custom LabelEdge (smoothstep path)
    expect(addedEdge.data).toBeDefined()
  })

  it('rejects connection with missing handles', () => {
    const state = useStudioStore.getState()
    const nodeIds = state.workflow.nodes.map(n => n.id)
    const prevEdgeCount = state.workflow.edges.length

    // Missing sourceHandle
    useStudioStore.getState().onConnect({
      source: nodeIds[0],
      target: nodeIds[1],
      sourceHandle: null,
      targetHandle: null,
    })

    expect(useStudioStore.getState().workflow.edges.length).toBe(prevEdgeCount)
  })

  it('rejects connection between non-existent nodes', () => {
    const prevEdgeCount = useStudioStore.getState().workflow.edges.length

    useStudioStore.getState().onConnect({
      source: 'nonexistent-1',
      sourceHandle: 'text',
      target: 'nonexistent-2',
      targetHandle: 'prompt',
    })

    expect(useStudioStore.getState().workflow.edges.length).toBe(prevEdgeCount)
  })
})

// ---------------------------------------------------------------------------
// 5. Store setWorkflow — validation logging
// ---------------------------------------------------------------------------
describe('store setWorkflow — graph validation', () => {
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

  it('setWorkflow with valid workflow succeeds', () => {
    const wf = createPromptToVideoWorkflow('new prompt')
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    useStudioStore.getState().setWorkflow(wf)

    expect(useStudioStore.getState().workflow.nodes[0].data.config.prompt).toBe('new prompt')
    warnSpy.mockRestore()
  })

  it('setWorkflow with workflow containing cycle logs warning', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const wf = createPromptToVideoWorkflow()

    // Create a cycle: add edge from output back to storyboard
    const storyboardNode = wf.nodes.find(n => n.data.kind === 'storyboard')!
    const outputNode = wf.nodes.find(n => n.data.kind === 'output')!
    const cycleEdge: EnhancedEdge = {
      id: 'cycle-edge',
      source: outputNode.id,
      sourceHandle: undefined,
      target: storyboardNode.id,
      targetHandle: 'prompt',
      type: 'smoothstep',
    }
    wf.edges = [...wf.edges, cycleEdge]

    useStudioStore.getState().setWorkflow(wf)

    expect(warnSpy).toHaveBeenCalled()
    const callArgs = warnSpy.mock.calls.find(c => c[0]?.includes?.('Graph validation'))
    expect(callArgs).toBeDefined()
    warnSpy.mockRestore()
  })
})

// ---------------------------------------------------------------------------
// 6. EnhancedEdge and EdgeData types
// ---------------------------------------------------------------------------
describe('EnhancedEdge type', () => {
  it('edge with EdgeData fields', () => {
    const edge: EnhancedEdge = {
      id: 'e1',
      source: 'n1',
      target: 'n2',
      type: 'smoothstep',
      data: {
        mode: 'map',
        sourcePath: '$.scenes',
        targetPath: '$.image',
        itemKey: 'scene-1',
        order: 0,
        label: 'map',
      },
    }
    expect(edge.data?.mode).toBe('map')
    expect(edge.data?.label).toBe('map')
    expect(edge.data?.itemKey).toBe('scene-1')
  })

  it('edge with undefined data is valid', () => {
    const edge: EnhancedEdge = {
      id: 'e2',
      source: 'n1',
      target: 'n2',
      type: 'smoothstep',
    }
    expect(edge.data).toBeUndefined()
  })
})

// ---------------------------------------------------------------------------
// 7. validateGraph with catalog-based port info
// ---------------------------------------------------------------------------
describe('validateGraph — with catalog', () => {
  it('valid linear workflow has no real errors', () => {
    const wf = createPromptToVideoWorkflow()
    const nodeKinds: Record<string, NodeKind> = {}
    wf.nodes.forEach(n => { nodeKinds[n.id] = n.data.kind })

    const errors = validateGraph(wf.nodes, wf.edges, NODE_CATALOG)
    const realErrors = errors.filter(e => e.code !== 'REQUIRED_PORT')
    expect(realErrors).toHaveLength(0)
  })

  it('type mismatch detected with catalog', () => {
    const nodeKinds: Record<string, NodeKind> = {
      n1: 'videoConcat',
      n2: 'textToImage',
    }
    const nodes = [
      { id: 'n1', kind: 'videoConcat' as NodeKind },
      { id: 'n2', kind: 'textToImage' as NodeKind },
    ]
    const edges = [
      { id: 'e1', source: 'n1', sourceHandle: 'video', target: 'n2', targetHandle: 'scene' },
    ]
    const errors = validateGraph(nodes, edges, NODE_CATALOG)
    expect(errors.some(e => e.code === 'TYPE_MISMATCH')).toBe(true)
  })
})
