import { describe, it, expect } from 'vitest'
import { validateGraph, validateConnection, getNodeEffectivePorts } from './graph-validation'
import { NODE_CATALOG } from './node-manifest'
import type { NodeKind, PortInfo } from '../types'

type NodeRecord = { id: string; kind: NodeKind; data?: { kind?: NodeKind; ports?: { inputs: PortInfo[]; outputs: PortInfo[] }; moduleId?: string; moduleVersion?: string } }
type EdgeRecord = { id: string; source: string; sourceHandle?: string; target: string; targetHandle?: string }

// Helper to create a node record
function node(id: string, kind: NodeKind): NodeRecord {
  return { id, kind }
}

// Helper to create an edge record
function edge(id: string, source: string, sourceHandle: string, target: string, targetHandle: string): EdgeRecord {
  return { id, source, sourceHandle, target, targetHandle }
}

function port(id: string, type: string, required = false, cardinality: 'one' | 'many' = 'one'): PortInfo {
  return { id, type, required, cardinality }
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

  it('unknown handle is rejected', () => {
    const nodes: NodeRecord[] = [
      node('n1', 'textInput'),
      node('n2', 'storyboard'),
    ]
    const edges: EdgeRecord[] = [
      edge('e1', 'n1', 'text', 'n2', 'not_a_port'),
    ]
    const errors = validateGraph(nodes, edges, NODE_CATALOG)
    const unknown = errors.filter((e) => e.code === 'UNKNOWN_HANDLE')
    expect(unknown.length).toBeGreaterThan(0)
    expect(unknown[0].portId).toBe('not_a_port')
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

  it('unknown handle returns error', () => {
    const result = validateConnection(
      'n1', 'text',
      'n2', 'not_a_port',
      kinds,
      NODE_CATALOG,
      [],
    )
    expect(result).not.toBeNull()
    expect(result!.code).toBe('UNKNOWN_HANDLE')
  })

  it('connect that would create a cycle is rejected at drag time', () => {
    const cycleKinds: Record<string, NodeKind> = { a: 'videoConcat', b: 'videoConcat' }
    const existingEdges: EdgeRecord[] = [
      { id: 'e1', source: 'a', sourceHandle: 'video', target: 'b', targetHandle: 'video' },
    ]
    // Closing the loop b -> a would create a cycle
    const result = validateConnection(
      'b', 'video',
      'a', 'video',
      cycleKinds,
      NODE_CATALOG,
      existingEdges,
    )
    expect(result).not.toBeNull()
    expect(result!.code).toBe('CYCLE')
  })

  it('non-closing connection is accepted', () => {
    const cycleKinds: Record<string, NodeKind> = { a: 'videoConcat', b: 'videoConcat', c: 'output' }
    const existingEdges: EdgeRecord[] = [
      { id: 'e1', source: 'a', sourceHandle: 'video', target: 'b', targetHandle: 'video' },
    ]
    const result = validateConnection(
      'b', 'video',
      'c', 'video',
      cycleKinds,
      NODE_CATALOG,
      existingEdges,
    )
    expect(result).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Effective ports (module-aware) — instance-level data.ports vs catalog fallback
// ---------------------------------------------------------------------------
describe('getNodeEffectivePorts', () => {
  it('falls back to the catalog when data.ports is missing', () => {
    const legacy = node('n1', 'textToImage')
    const ports = getNodeEffectivePorts(legacy, NODE_CATALOG)
    expect(ports.inputs.map((p) => p.id)).toEqual(['scene'])
    expect(ports.outputs.map((p) => p.id)).toEqual(['image'])
  })

  it('prefers instance-level data.ports over the catalog', () => {
    const moduleNode: NodeRecord = {
      id: 'm1',
      kind: 'textToImage',
      data: {
        kind: 'textToImage',
        moduleId: 'builtin.seedream.text-to-image',
        ports: {
          inputs: [port('scene', 'scene', true), port('style', 'text')],
          outputs: [port('image', 'image'), port('thumb', 'image')],
        },
      },
    }
    const ports = getNodeEffectivePorts(moduleNode, NODE_CATALOG)
    expect(ports.inputs.map((p) => p.id)).toEqual(['scene', 'style'])
    expect(ports.outputs.map((p) => p.id)).toEqual(['image', 'thumb'])
  })

  it('returns empty ports for unknown nodes', () => {
    const ports = getNodeEffectivePorts(undefined, NODE_CATALOG)
    expect(ports.inputs).toHaveLength(0)
    expect(ports.outputs).toHaveLength(0)
  })
})

// ---------------------------------------------------------------------------
// Module-instance nodes — extension ports are type/cardinality-checked
// ---------------------------------------------------------------------------
describe('module-aware connection validation', () => {
  const moduleNode: NodeRecord = {
    id: 'm1',
    kind: 'textToImage',
    data: {
      kind: 'textToImage',
      moduleId: 'builtin.seedream.text-to-image',
      moduleVersion: '1.0.0',
      ports: {
        inputs: [port('scene', 'scene', true), port('style', 'text')],
        outputs: [port('image', 'image'), port('thumb', 'image')],
      },
    },
  }
  const textNode = node('t1', 'textInput')
  const videoNode = node('v1', 'videoConcat')
  const itvNode = node('i1', 'imageToVideo')
  const nodes: NodeRecord[] = [moduleNode, textNode, videoNode, itvNode]

  it('accepts a connection into an extension input when types match', () => {
    const result = validateConnection(
      't1', 'text',
      'm1', 'style',
      nodes, NODE_CATALOG, [],
    )
    expect(result).toBeNull()
  })

  it('rejects a connection into an extension input when types mismatch', () => {
    const result = validateConnection(
      'v1', 'video',
      'm1', 'style',
      nodes, NODE_CATALOG, [],
    )
    expect(result).not.toBeNull()
    expect(result!.code).toBe('TYPE_MISMATCH')
  })

  it('accepts a connection from an extension output when types match', () => {
    const result = validateConnection(
      'm1', 'thumb',
      'i1', 'image',
      nodes, NODE_CATALOG, [],
    )
    expect(result).toBeNull()
  })

  it('rejects a connection from an extension output when types mismatch', () => {
    const sbNode = node('s1', 'storyboard')
    const result = validateConnection(
      'm1', 'thumb',   // image (extension output)
      's1', 'prompt',  // text
      [...nodes, sbNode], NODE_CATALOG, [],
    )
    expect(result).not.toBeNull()
    expect(result!.code).toBe('TYPE_MISMATCH')
    expect(result!.portId).toBe('prompt')
  })

  it('rejects handles that are not in the module instance ports', () => {
    const result = validateConnection(
      'm1', 'not_a_port',
      'i1', 'image',
      nodes, NODE_CATALOG, [],
    )
    expect(result).not.toBeNull()
    expect(result!.code).toBe('UNKNOWN_HANDLE')
    expect(result!.portId).toBe('not_a_port')
  })

  it('respects a core-port cardinality override from data.ports', () => {
    // storyboard.prompt is cardinality "one" in the catalog, but this instance
    // overrides it to "many" — a second edge must be accepted.
    const wideStoryboard: NodeRecord = {
      id: 'sb',
      kind: 'storyboard',
      data: {
        kind: 'storyboard',
        ports: {
          inputs: [port('prompt', 'text', true, 'many')],
          outputs: [port('scenes', 'scene', false, 'many')],
        },
      },
    }
    const existingEdges: EdgeRecord[] = [
      { id: 'e1', source: 't1', sourceHandle: 'text', target: 'sb', targetHandle: 'prompt' },
    ]
    const text2 = node('t2', 'textInput')
    const result2 = validateConnection(
      't2', 'text',
      'sb', 'prompt',
      [...nodes, wideStoryboard, text2], NODE_CATALOG, existingEdges,
    )
    expect(result2).toBeNull()

    // Without the override, the catalog's "one" cardinality rejects it
    const plainStoryboard = node('sb2', 'storyboard')
    const result3 = validateConnection(
      't2', 'text',
      'sb2', 'prompt',
      [...nodes, plainStoryboard, text2], NODE_CATALOG,
      [{ id: 'e1', source: 't1', sourceHandle: 'text', target: 'sb2', targetHandle: 'prompt' }],
    )
    expect(result3).not.toBeNull()
    expect(result3!.code).toBe('CARDINALITY_VIOLATION')
  })

  it('validateGraph checks module extension ports too', () => {
    const edges: EdgeRecord[] = [
      edge('e1', 't1', 'text', 'm1', 'style'),   // text -> text OK
      edge('e2', 'v1', 'video', 'm1', 'scene'),  // video -> scene mismatch
      edge('e3', 'm1', 'ghost', 'i1', 'image'),  // unknown source handle
    ]
    const errors = validateGraph(nodes, edges, NODE_CATALOG)
    const codes = errors.map((e) => e.code)
    expect(codes).toContain('TYPE_MISMATCH')
    expect(codes).toContain('UNKNOWN_HANDLE')
    // The valid extension edge must not be flagged
    const edgeErrors = errors.filter((e) => e.edgeId === 'e1')
    expect(edgeErrors).toHaveLength(0)
  })
})
