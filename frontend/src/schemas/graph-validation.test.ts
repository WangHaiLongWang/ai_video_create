import { describe, it, expect } from 'vitest'
import { validateGraph, validateConnection } from './graph-validation'
import { NODE_CATALOG } from './node-manifest'
import type { NodeKind } from '../types'

type NodeRecord = { id: string; kind: NodeKind }
type EdgeRecord = { id: string; source: string; sourceHandle?: string; target: string; targetHandle?: string }

// Helper to create a node record
function node(id: string, kind: NodeKind): NodeRecord {
  return { id, kind }
}

// Helper to create an edge record
function edge(id: string, source: string, sourceHandle: string, target: string, targetHandle: string): EdgeRecord {
  return { id, source, sourceHandle, target, targetHandle }
}

describe('validateGraph', () => {
  it('valid linear graph passes', () => {
    const nodes: NodeRecord[] = [
      node('n1', 'textInput'),
      node('n2', 'storyboard'),
      node('n3', 'textToImage'),
      node('n4', 'imageToVideo'),
      node('n5', 'videoConcat'),
      node('n6', 'output'),
    ]
    const edges: EdgeRecord[] = [
      edge('e1', 'n1', 'text', 'n2', 'prompt'),
      edge('e2', 'n2', 'scenes', 'n3', 'scene'),
      edge('e3', 'n3', 'image', 'n4', 'image'),
      edge('e4', 'n4', 'video', 'n5', 'video'),
      edge('e5', 'n5', 'video', 'n6', 'video'),
    ]
    // Required port warnings are expected for nodes not fully connected
    const errors = validateGraph(nodes, edges, NODE_CATALOG)
    // Should have no errors (only warnings for required ports on unconnected optional paths)
    const realErrors = errors.filter((e) => e.code !== 'REQUIRED_PORT')
    expect(realErrors).toHaveLength(0)
  })

  it('self-loop is rejected', () => {
    const nodes: NodeRecord[] = [
      node('n1', 'textInput'),
    ]
    const edges: EdgeRecord[] = [
      edge('e1', 'n1', 'text', 'n1', 'text'),
    ]
    const errors = validateGraph(nodes, edges, NODE_CATALOG)
    expect(errors.some((e) => e.code === 'SELF_LOOP')).toBe(true)
  })

  it('duplicate edge is rejected', () => {
    const nodes: NodeRecord[] = [
      node('n1', 'textInput'),
      node('n2', 'storyboard'),
    ]
    const edges: EdgeRecord[] = [
      edge('e1', 'n1', 'text', 'n2', 'prompt'),
      edge('e2', 'n1', 'text', 'n2', 'prompt'),
    ]
    const errors = validateGraph(nodes, edges, NODE_CATALOG)
    expect(errors.some((e) => e.code === 'DUPLICATE_EDGE')).toBe(true)
  })

  it('type mismatch is rejected (video -> image)', () => {
    const nodes: NodeRecord[] = [
      node('n1', 'videoConcat'),
      node('n2', 'textToImage'),
    ]
    const edges: EdgeRecord[] = [
      edge('e1', 'n1', 'video', 'n2', 'scene'),
    ]
    const errors = validateGraph(nodes, edges, NODE_CATALOG)
    expect(errors.some((e) => e.code === 'TYPE_MISMATCH')).toBe(true)
  })

  it('cardinality violation (two edges to one "one" input)', () => {
    const nodes: NodeRecord[] = [
      node('n1', 'textInput'),
      node('n2', 'textInput'),
      node('n3', 'storyboard'),
    ]
    const edges: EdgeRecord[] = [
      edge('e1', 'n1', 'text', 'n3', 'prompt'),
      edge('e2', 'n2', 'text', 'n3', 'prompt'),
    ]
    const errors = validateGraph(nodes, edges, NODE_CATALOG)
    expect(errors.some((e) => e.code === 'CARDINALITY_VIOLATION')).toBe(true)
  })

  it('cycle detection (A -> B -> C -> A)', () => {
    const nodes: NodeRecord[] = [
      node('n1', 'storyboard'),
      node('n2', 'textToImage'),
      node('n3', 'imageToVideo'),
    ]
    // storyboard scenes -> textToImage scene (valid type)
    // textToImage image -> imageToVideo image (valid type)
    // imageToVideo video -> storyboard prompt (type mismatch but we test cycle)
    const edges: EdgeRecord[] = [
      edge('e1', 'n1', 'scenes', 'n2', 'scene'),
      edge('e2', 'n2', 'image', 'n3', 'image'),
      edge('e3', 'n3', 'video', 'n1', 'prompt'),
    ]
    const errors = validateGraph(nodes, edges, NODE_CATALOG)
    expect(errors.some((e) => e.code === 'CYCLE')).toBe(true)
  })

  it('"any" type accepts anything', () => {
    // We need to create a custom manifest with "any" type
    const customCatalog = {
      ...NODE_CATALOG,
      textInput: {
        ...NODE_CATALOG.textInput,
        ports: {
          inputs: [],
          outputs: [{ id: 'text', type: 'any' as const, required: false, cardinality: 'one' as const }],
        },
      },
    }
    const nodes: NodeRecord[] = [
      node('n1', 'textInput'),
      node('n2', 'videoConcat'),
    ]
    const edges: EdgeRecord[] = [
      edge('e1', 'n1', 'text', 'n2', 'video'),
    ]
    const errors = validateGraph(nodes, edges, customCatalog)
    expect(errors.some((e) => e.code === 'TYPE_MISMATCH')).toBe(false)
  })

  it('required port warning', () => {
    const nodes: NodeRecord[] = [
      node('n1', 'textInput'),
      node('n2', 'storyboard'),
    ]
    const edges: EdgeRecord[] = [] // no connections
    const errors = validateGraph(nodes, edges, NODE_CATALOG)
    // storyboard has required input "prompt" — should generate REQUIRED_PORT warning
    const requiredWarnings = errors.filter((e) => e.code === 'REQUIRED_PORT')
    expect(requiredWarnings.length).toBeGreaterThan(0)
  })

  it('direction check rejects input-to-input', () => {
    const nodes: NodeRecord[] = [
      node('n1', 'imageToVideo'),
      node('n2', 'storyboard'),
    ]
    // Trying to connect imageToVideo.scene (input) -> storyboard.prompt (input)
    const edges: EdgeRecord[] = [
      edge('e1', 'n1', 'scene', 'n2', 'prompt'),
    ]
    const errors = validateGraph(nodes, edges, NODE_CATALOG)
    expect(errors.some((e) => e.code === 'DIRECTION')).toBe(true)
  })

  it('direction check rejects output-to-output', () => {
    const nodes: NodeRecord[] = [
      node('n1', 'textInput'),
      node('n2', 'textToImage'),
    ]
    // Trying to connect textInput.text (output) -> textToImage.image (output)
    const edges: EdgeRecord[] = [
      edge('e1', 'n1', 'text', 'n2', 'image'),
    ]
    const errors = validateGraph(nodes, edges, NODE_CATALOG)
    expect(errors.some((e) => e.code === 'DIRECTION')).toBe(true)
  })
})

describe('validateConnection', () => {
  const kinds: Record<string, NodeKind> = {
    n1: 'textInput',
    n2: 'storyboard',
    n3: 'videoConcat',
    n4: 'textToImage',
  }

  it('valid connection returns null', () => {
    const result = validateConnection(
      'n1', 'text',
      'n2', 'prompt',
      kinds,
      NODE_CATALOG,
      [],
    )
    expect(result).toBeNull()
  })

  it('self-loop returns error', () => {
    const result = validateConnection(
      'n1', 'text',
      'n1', 'text',
      kinds,
      NODE_CATALOG,
      [],
    )
    expect(result).not.toBeNull()
    expect(result!.code).toBe('SELF_LOOP')
  })

  it('duplicate connection returns error', () => {
    const existingEdges: EdgeRecord[] = [
      { id: 'e1', source: 'n1', sourceHandle: 'text', target: 'n2', targetHandle: 'prompt' },
    ]
    const result = validateConnection(
      'n1', 'text',
      'n2', 'prompt',
      kinds,
      NODE_CATALOG,
      existingEdges,
    )
    expect(result).not.toBeNull()
    expect(result!.code).toBe('DUPLICATE_EDGE')
  })

  it('type mismatch returns error', () => {
    // videoConcat output (video) -> textToImage input (scene) is a mismatch
    const result = validateConnection(
      'n3', 'video',
      'n4', 'scene',
      kinds,
      NODE_CATALOG,
      [],
    )
    expect(result).not.toBeNull()
    expect(result!.code).toBe('TYPE_MISMATCH')
  })

  it('cardinality violation on "one" port returns error', () => {
    // Use a different source node so it's not a duplicate edge
    const kindsWithExtra: Record<string, NodeKind> = { ...kinds, n5: 'textInput' }
    const existingEdges: EdgeRecord[] = [
      { id: 'e1', source: 'n1', sourceHandle: 'text', target: 'n2', targetHandle: 'prompt' },
    ]
    const result = validateConnection(
      'n5', 'text',
      'n2', 'prompt',
      kindsWithExtra,
      NODE_CATALOG,
      existingEdges,
    )
    expect(result).not.toBeNull()
    expect(result!.code).toBe('CARDINALITY_VIOLATION')
  })
})
