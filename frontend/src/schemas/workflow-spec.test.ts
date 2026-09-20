import { describe, it, expect } from 'vitest'
import type { StudioNode, EnhancedEdge, FieldDefinition, WorkflowSpec } from '../types'
import {
  isV1,
  migrateV1toV2,
  upgradeWorkflowSpec,
  downgradeWorkflowSpec,
  type WorkflowSpecV1,
  type WorkflowSpecV2,
} from './workflow-spec'
import { createPromptToVideoWorkflow, createNode } from '../workflow'
import { NODE_CATALOG } from './node-manifest'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeNode(id: string, kind: import('../types').NodeKind): StudioNode {
  return {
    id,
    type: 'studio',
    position: { x: 0, y: 0 },
    data: {
      label: kind,
      description: '',
      kind,
      status: 'idle',
      config: {},
    },
  }
}

// ---------------------------------------------------------------------------
// isV1
// ---------------------------------------------------------------------------

describe('isV1', () => {
  it('returns true for a v1 spec', () => {
    expect(isV1({ schemaVersion: '1.0' })).toBe(true)
  })

  it('returns true for a spec with no schemaVersion', () => {
    expect(isV1({})).toBe(true)
  })

  it('returns false for a v2 spec', () => {
    expect(isV1({ schemaVersion: '2.0' })).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// migrateV1toV2
// ---------------------------------------------------------------------------

describe('migrateV1toV2', () => {
  it('adds default handles to edges without them', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [makeNode('n1', 'textInput'), makeNode('n2', 'storyboard')],
      edges: [{
        id: 'e1',
        source: 'n1',
        target: 'n2',
        type: 'smoothstep',
      }],
    }

    const v2 = migrateV1toV2(v1)
    expect(v2.schemaVersion).toBe('2.0')
    expect(v2.edges[0].sourceHandle).toBe('text')
    expect(v2.edges[0].targetHandle).toBe('prompt')
  })

  it('preserves existing handles', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [makeNode('n1', 'textInput'), makeNode('n2', 'storyboard')],
      edges: [{
        id: 'e1',
        source: 'n1',
        sourceHandle: 'text',
        target: 'n2',
        targetHandle: 'prompt',
        type: 'smoothstep',
      }],
    }

    const v2 = migrateV1toV2(v1)
    expect(v2.edges[0].sourceHandle).toBe('text')
    expect(v2.edges[0].targetHandle).toBe('prompt')
  })

  it('adds viewport and metadata', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [],
      edges: [],
    }

    const v2 = migrateV1toV2(v1)
    expect(v2.viewport).toEqual({ x: 0, y: 0, zoom: 1 })
    expect(v2.metadata).toBeDefined()
    expect(v2.metadata.tags).toEqual([])
    expect(v2.metadata.createdAt).toBeDefined()
  })

  it('adds default edge data when missing', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [makeNode('n1', 'textInput'), makeNode('n2', 'storyboard')],
      edges: [{
        id: 'e1',
        source: 'n1',
        target: 'n2',
        type: 'smoothstep',
      }],
    }

    const v2 = migrateV1toV2(v1)
    expect(v2.edges[0].data).toEqual({ mode: 'direct', label: '' })
  })

  it('preserves existing edge data', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [makeNode('n1', 'textInput'), makeNode('n2', 'storyboard')],
      edges: [{
        id: 'e1',
        source: 'n1',
        sourceHandle: 'text',
        target: 'n2',
        targetHandle: 'prompt',
        type: 'smoothstep',
        data: { mode: 'map', label: 'custom' },
      }],
    }

    const v2 = migrateV1toV2(v1)
    expect(v2.edges[0].data?.mode).toBe('map')
    expect(v2.edges[0].data?.label).toBe('custom')
  })

  it('populates ports on nodes that lack them', () => {
    const node = makeNode('n1', 'textInput')
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [node],
      edges: [],
    }

    const v2 = migrateV1toV2(v1)
    expect(v2.nodes[0].data.ports).toBeDefined()
    expect(v2.nodes[0].data.ports!.outputs).toHaveLength(1)
    expect(v2.nodes[0].data.ports!.outputs[0].id).toBe('text')
  })

  it('does not overwrite existing ports', () => {
    const node = makeNode('n1', 'textInput')
    node.data.ports = {
      inputs: [],
      outputs: [{ id: 'custom', type: 'text', required: false, cardinality: 'one' }],
    }
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [node],
      edges: [],
    }

    const v2 = migrateV1toV2(v1)
    expect(v2.nodes[0].data.ports!.outputs[0].id).toBe('custom')
  })

  it('sets manifestVersion', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [],
      edges: [],
    }

    const v2 = migrateV1toV2(v1)
    expect(v2.manifestVersion).toBe('1.0')
  })
})

// ---------------------------------------------------------------------------
// upgradeWorkflowSpec
// ---------------------------------------------------------------------------

describe('upgradeWorkflowSpec', () => {
  it('auto-detects v1 and migrates', () => {
    const v1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [makeNode('n1', 'textInput'), makeNode('n2', 'storyboard')],
      edges: [{
        id: 'e1',
        source: 'n1',
        target: 'n2',
        type: 'smoothstep',
      }],
    }

    const v2 = upgradeWorkflowSpec(v1)
    expect(v2.schemaVersion).toBe('2.0')
    expect(v2.edges[0].sourceHandle).toBe('text')
  })

  it('passes through v2 specs unchanged', () => {
    const v2: WorkflowSpecV2 = {
      schemaVersion: '2.0',
      manifestVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [],
      edges: [],
      viewport: { x: 10, y: 20, zoom: 2 },
      metadata: { tags: ['test'] },
    }

    const result = upgradeWorkflowSpec(v2)
    expect(result).toBe(v2)
  })

  it('auto-detects missing schemaVersion as v1', () => {
    const spec = {
      id: 'test',
      name: 'Test',
      nodes: [],
      edges: [],
    }

    const v2 = upgradeWorkflowSpec(spec)
    expect(v2.schemaVersion).toBe('2.0')
    expect(v2.manifestVersion).toBe('1.0')
  })

  it('v1 → v2 migration preserves node data', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [
        {
          id: 'n1',
          type: 'studio',
          position: { x: 100, y: 200 },
          data: {
            label: 'My Input',
            description: 'desc',
            kind: 'textInput',
            status: 'idle',
            config: { prompt: 'hello' },
          },
        },
      ],
      edges: [],
    }

    const v2 = migrateV1toV2(v1)
    expect(v2.nodes[0].id).toBe('n1')
    expect(v2.nodes[0].data.label).toBe('My Input')
    expect(v2.nodes[0].data.description).toBe('desc')
    expect(v2.nodes[0].data.kind).toBe('textInput')
    expect(v2.nodes[0].data.config.prompt).toBe('hello')
    expect(v2.nodes[0].position).toEqual({ x: 100, y: 200 })
  })

  it('v1 edges get sourceHandle/targetHandle from NODE_CATALOG', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [makeNode('n1', 'textInput'), makeNode('n2', 'storyboard')],
      edges: [{
        id: 'e1',
        source: 'n1',
        target: 'n2',
        type: 'smoothstep',
      }],
    }

    const v2 = migrateV1toV2(v1)
    const edge = v2.edges[0]
    expect(edge.sourceHandle).toBe(NODE_CATALOG.textInput.ports.outputs[0].id)
    expect(edge.targetHandle).toBe(NODE_CATALOG.storyboard.ports.inputs[0].id)
  })

  it('v2 → v2 passthrough does not mutate original', () => {
    const v2: WorkflowSpecV2 = {
      schemaVersion: '2.0',
      manifestVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [makeNode('n1', 'textInput')],
      edges: [],
      viewport: { x: 5, y: 10, zoom: 1.5 },
      metadata: { tags: ['hello'] },
    }

    const result = upgradeWorkflowSpec(v2)
    expect(result).toBe(v2)
    expect(result.nodes[0].data.kind).toBe('textInput')
    expect(result.viewport).toEqual({ x: 5, y: 10, zoom: 1.5 })
  })
})

// ---------------------------------------------------------------------------
// downgradeWorkflowSpec
// ---------------------------------------------------------------------------

describe('downgradeWorkflowSpec', () => {
  it('downgrades v2 → v1 with schemaVersion 1.0', () => {
    const v2: WorkflowSpecV2 = {
      schemaVersion: '2.0',
      manifestVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [makeNode('n1', 'textInput')],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      metadata: { tags: [] },
    }

    const v1 = downgradeWorkflowSpec(v2)
    expect(v1.schemaVersion).toBe('1.0')
    expect(v1.id).toBe('test')
    expect(v1.name).toBe('Test')
  })

  it('strips sourceHandle/targetHandle from edges', () => {
    const v2: WorkflowSpecV2 = {
      schemaVersion: '2.0',
      manifestVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [makeNode('n1', 'textInput'), makeNode('n2', 'storyboard')],
      edges: [{
        id: 'e1',
        source: 'n1',
        target: 'n2',
        sourceHandle: 'text',
        targetHandle: 'prompt',
        type: 'smoothstep',
      }],
      viewport: { x: 0, y: 0, zoom: 1 },
      metadata: { tags: [] },
    }

    const v1 = downgradeWorkflowSpec(v2)
    expect(v1.edges[0].sourceHandle).toBeUndefined()
    expect(v1.edges[0].targetHandle).toBeUndefined()
    expect(v1.edges[0].source).toBe('n1')
    expect(v1.edges[0].target).toBe('n2')
  })

  it('strips ports from nodes', () => {
    const v2: WorkflowSpecV2 = {
      schemaVersion: '2.0',
      manifestVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [makeNode('n1', 'textInput')],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      metadata: { tags: [] },
    }
    // Migrate first to populate ports
    const v2WithPorts = migrateV1toV2({
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [makeNode('n1', 'textInput')],
      edges: [],
    })

    const v1 = downgradeWorkflowSpec(v2WithPorts)
    expect(v1.nodes[0].data.ports).toBeUndefined()
  })

  it('preserves fieldSchema through downgrade', () => {
    const node = makeNode('n1', 'textInput')
    node.data.fieldSchema = [
      { id: 'my_field', label: 'My Field', type: 'text', default: 'test-val' },
    ]
    node.data.config = { my_field: 'test-val' }

    const v2: WorkflowSpecV2 = {
      schemaVersion: '2.0',
      manifestVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [node],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      metadata: { tags: [] },
    }

    const v1 = downgradeWorkflowSpec(v2)
    expect(v1.nodes[0].data.fieldSchema).toEqual([
      { id: 'my_field', label: 'My Field', type: 'text', default: 'test-val' },
    ])
    expect(v1.nodes[0].data.config.my_field).toBe('test-val')
  })

  it('roundtrip v1 → v2 → v1 preserves fieldSchema', () => {
    const originalNode = makeNode('n1', 'textInput')
    originalNode.data.fieldSchema = [
      { id: 'custom_text', label: 'Custom Text', type: 'text', required: true },
      { id: 'custom_num', label: 'Custom Num', type: 'number', default: 42 },
    ]
    originalNode.data.config = { custom_text: 'hello', custom_num: 42 }

    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [originalNode],
      edges: [],
    }

    // Upgrade
    const v2 = upgradeWorkflowSpec(v1)
    expect(v2.nodes[0].data.fieldSchema).toHaveLength(2)
    expect(v2.nodes[0].data.fieldSchema![0].id).toBe('custom_text')
    expect(v2.nodes[0].data.fieldSchema![1].id).toBe('custom_num')
    expect(v2.nodes[0].data.config.custom_text).toBe('hello')

    // Downgrade
    const v1Again = downgradeWorkflowSpec(v2 as WorkflowSpecV2)
    expect(v1Again.nodes[0].data.fieldSchema).toHaveLength(2)
    expect(v1Again.nodes[0].data.fieldSchema![0].id).toBe('custom_text')
    expect(v1Again.nodes[0].data.fieldSchema![0].type).toBe('text')
    expect(v1Again.nodes[0].data.config.custom_text).toBe('hello')
    expect(v1Again.nodes[0].data.config.custom_num).toBe(42)
  })
})

// ---------------------------------------------------------------------------
// createPromptToVideoWorkflow
// ---------------------------------------------------------------------------

describe('createPromptToVideoWorkflow', () => {
  it('returns v2 format', () => {
    const wf = createPromptToVideoWorkflow()
    expect(wf.schemaVersion).toBe('2.0')
    expect(wf.manifestVersion).toBe('1.0')
    expect(wf.viewport).toEqual({ x: 0, y: 0, zoom: 1 })
    expect(wf.metadata).toBeDefined()
  })

  it('edges have correct sourceHandle/targetHandle', () => {
    const wf = createPromptToVideoWorkflow()

    // textInput -> storyboard
    expect(wf.edges[0].sourceHandle).toBe('text')
    expect(wf.edges[0].targetHandle).toBe('prompt')

    // storyboard -> textToImage
    expect(wf.edges[1].sourceHandle).toBe('scenes')
    expect(wf.edges[1].targetHandle).toBe('scene')
  })

  it('edges have data with mode and label', () => {
    const wf = createPromptToVideoWorkflow()
    for (const edge of wf.edges) {
      expect(edge.data).toBeDefined()
      expect(edge.data?.mode).toBe('direct')
      expect(edge.data?.label).toBe('')
    }
  })

  it('has 6 nodes and 5 edges', () => {
    const wf = createPromptToVideoWorkflow()
    expect(wf.nodes).toHaveLength(6)
    expect(wf.edges).toHaveLength(5)
  })

  it('with prompt sets name containing prompt', () => {
    const wf = createPromptToVideoWorkflow('测试提示词')
    expect(wf.name).toContain('测试提示词')
  })

  it('metadata has default tag', () => {
    const wf = createPromptToVideoWorkflow()
    expect(wf.metadata.tags).toContain('default')
  })
})

// ---------------------------------------------------------------------------
// Helpers for roundtrip tests
// ---------------------------------------------------------------------------

/** Simulate JSON roundtrip: serialize to JSON string then parse back */
function jsonRoundtrip<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj))
}

/** Create a v2 spec with custom fields and edge data for comprehensive testing */
function makeComplexV2Spec(): WorkflowSpecV2 {
  const node1 = makeNode('n1', 'textInput')
  node1.data.config = { prompt: 'rain city at night' }
  node1.data.fieldSchema = [
    { id: 'scene_count', label: 'Scene Count', type: 'number', default: 5, required: true },
    { id: 'style', label: 'Style', type: 'select', options: [{ label: 'Noir', value: 'noir' }, { label: 'Cyberpunk', value: 'cyberpunk' }] },
  ]

  const node2 = makeNode('n2', 'storyboard')
  node2.data.config = { provider: 'Mock', scenes: 5, style: 'cinematic noir' }

  const node3 = makeNode('n3', 'textToImage')
  node3.data.config = { ratio: '16:9', mapOver: true }

  return {
    schemaVersion: '2.0',
    manifestVersion: '1.0',
    id: 'complex-test',
    name: 'Complex Test Workflow',
    description: 'A workflow for roundtrip testing',
    nodes: [node1, node2, node3],
    edges: [
      {
        id: 'e1',
        source: 'n1',
        sourceHandle: 'text',
        target: 'n2',
        targetHandle: 'prompt',
        type: 'smoothstep',
        data: { mode: 'direct', label: 'topic', sourcePath: '$.prompt', targetPath: '$.input' },
      },
      {
        id: 'e2',
        source: 'n2',
        sourceHandle: 'scenes',
        target: 'n3',
        targetHandle: 'scene',
        type: 'smoothstep',
        data: { mode: 'map', label: 'per-scene', order: 1 },
      },
    ],
    viewport: { x: -50, y: 30, zoom: 1.5 },
    metadata: {
      tags: ['test', 'roundtrip'],
      createdBy: 'test-user',
      createdAt: '2025-01-15T10:00:00Z',
      updatedAt: '2025-01-15T11:00:00Z',
      customKey: 'customValue',
    },
  }
}

// ---------------------------------------------------------------------------
// Roundtrip: Empty workflow (v2 -> JSON -> v2)
// ---------------------------------------------------------------------------

describe('Roundtrip: empty workflow', () => {
  it('v2 JSON roundtrip preserves all fields', () => {
    const original: WorkflowSpecV2 = {
      schemaVersion: '2.0',
      manifestVersion: '1.0',
      id: 'empty-wf',
      name: 'Empty Workflow',
      nodes: [],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      metadata: { tags: [] },
    }

    const roundtripped = jsonRoundtrip<WorkflowSpecV2>(original)

    expect(roundtripped.schemaVersion).toBe('2.0')
    expect(roundtripped.manifestVersion).toBe('1.0')
    expect(roundtripped.id).toBe('empty-wf')
    expect(roundtripped.name).toBe('Empty Workflow')
    expect(roundtripped.nodes).toHaveLength(0)
    expect(roundtripped.edges).toHaveLength(0)
    expect(roundtripped.viewport).toEqual({ x: 0, y: 0, zoom: 1 })
    expect(roundtripped.metadata.tags).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// Roundtrip: 6-node default workflow (create -> JSON -> verify)
// ---------------------------------------------------------------------------

describe('Roundtrip: 6-node default workflow', () => {
  it('preserves all nodes, edges, viewport, metadata through JSON roundtrip', () => {
    const wf = createPromptToVideoWorkflow()
    const roundtripped = jsonRoundtrip<WorkflowSpecV2>(wf)

    // Schema
    expect(roundtripped.schemaVersion).toBe('2.0')
    expect(roundtripped.manifestVersion).toBe('1.0')
    expect(roundtripped.id).toBe(wf.id)

    // Nodes
    expect(roundtripped.nodes).toHaveLength(6)
    for (let i = 0; i < 6; i++) {
      expect(roundtripped.nodes[i].id).toBe(wf.nodes[i].id)
      expect(roundtripped.nodes[i].data.kind).toBe(wf.nodes[i].data.kind)
      expect(roundtripped.nodes[i].data.label).toBe(wf.nodes[i].data.label)
      expect(roundtripped.nodes[i].position).toEqual(wf.nodes[i].position)
    }

    // Edges with handles
    expect(roundtripped.edges).toHaveLength(5)
    for (let i = 0; i < 5; i++) {
      expect(roundtripped.edges[i].sourceHandle).toBe(wf.edges[i].sourceHandle)
      expect(roundtripped.edges[i].targetHandle).toBe(wf.edges[i].targetHandle)
      expect(roundtripped.edges[i].source).toBe(wf.edges[i].source)
      expect(roundtripped.edges[i].target).toBe(wf.edges[i].target)
      expect(roundtripped.edges[i].data?.mode).toBe('direct')
      expect(roundtripped.edges[i].data?.label).toBe('')
    }

    // Viewport
    expect(roundtripped.viewport).toEqual({ x: 0, y: 0, zoom: 1 })

    // Metadata
    expect(roundtripped.metadata.tags).toContain('default')
  })

  it('node config values survive JSON roundtrip', () => {
    const wf = createPromptToVideoWorkflow()
    const roundtripped = jsonRoundtrip<WorkflowSpecV2>(wf)

    // textInput config
    const textInput = roundtripped.nodes.find(n => n.data.kind === 'textInput')
    expect(textInput?.data.config.prompt).toBe(wf.nodes[0].data.config.prompt)

    // storyboard config
    const storyboard = roundtripped.nodes.find(n => n.data.kind === 'storyboard')
    expect(storyboard?.data.config.provider).toBe('Mock')
    expect(storyboard?.data.config.scenes).toBe(5)
  })

  it('node ports survive JSON roundtrip', () => {
    const wf = createPromptToVideoWorkflow()
    const roundtripped = jsonRoundtrip<WorkflowSpecV2>(wf)

    for (const node of roundtripped.nodes) {
      const origNode = wf.nodes.find(n => n.id === node.id)
      expect(node.data.ports).toBeDefined()
      expect(node.data.ports!.inputs).toEqual(origNode!.data.ports!.inputs)
      expect(node.data.ports!.outputs).toEqual(origNode!.data.ports!.outputs)
    }
  })
})

// ---------------------------------------------------------------------------
// Roundtrip: Workflow with custom fields
// ---------------------------------------------------------------------------

describe('Roundtrip: workflow with custom fields', () => {
  it('fieldSchema and config survive JSON roundtrip', () => {
    const wf = makeComplexV2Spec()
    const roundtripped = jsonRoundtrip<WorkflowSpecV2>(wf)

    const node1 = roundtripped.nodes.find(n => n.id === 'n1')
    expect(node1).toBeDefined()
    expect(node1!.data.fieldSchema).toHaveLength(2)
    expect(node1!.data.fieldSchema![0].id).toBe('scene_count')
    expect(node1!.data.fieldSchema![0].type).toBe('number')
    expect(node1!.data.fieldSchema![0].default).toBe(5)
    expect(node1!.data.fieldSchema![0].required).toBe(true)
    expect(node1!.data.fieldSchema![1].id).toBe('style')
    expect(node1!.data.fieldSchema![1].options).toHaveLength(2)

    expect(node1!.data.config.prompt).toBe('rain city at night')
  })

  it('edge data (mode, label, sourcePath, targetPath) survive JSON roundtrip', () => {
    const wf = makeComplexV2Spec()
    const roundtripped = jsonRoundtrip<WorkflowSpecV2>(wf)

    expect(roundtripped.edges[0].data?.mode).toBe('direct')
    expect(roundtripped.edges[0].data?.label).toBe('topic')
    expect(roundtripped.edges[0].data?.sourcePath).toBe('$.prompt')
    expect(roundtripped.edges[0].data?.targetPath).toBe('$.input')

    expect(roundtripped.edges[1].data?.mode).toBe('map')
    expect(roundtripped.edges[1].data?.label).toBe('per-scene')
    expect(roundtripped.edges[1].data?.order).toBe(1)
  })

  it('viewport with non-default values survives JSON roundtrip', () => {
    const wf = makeComplexV2Spec()
    const roundtripped = jsonRoundtrip<WorkflowSpecV2>(wf)

    expect(roundtripped.viewport).toEqual({ x: -50, y: 30, zoom: 1.5 })
  })

  it('metadata with custom keys survives JSON roundtrip', () => {
    const wf = makeComplexV2Spec()
    const roundtripped = jsonRoundtrip<WorkflowSpecV2>(wf)

    expect(roundtripped.metadata.tags).toEqual(['test', 'roundtrip'])
    expect(roundtripped.metadata.createdBy).toBe('test-user')
    expect(roundtripped.metadata.createdAt).toBe('2025-01-15T10:00:00Z')
    expect(roundtripped.metadata.updatedAt).toBe('2025-01-15T11:00:00Z')
    expect(roundtripped.metadata.customKey).toBe('customValue')
  })

  it('node inputType and outputType survive JSON roundtrip', () => {
    const wf = makeComplexV2Spec()
    const roundtripped = jsonRoundtrip<WorkflowSpecV2>(wf)

    for (const node of roundtripped.nodes) {
      const orig = wf.nodes.find(n => n.id === node.id)
      expect(node.data.inputType).toBe(orig!.data.inputType)
      expect(node.data.outputType).toBe(orig!.data.outputType)
    }
  })
})

// ---------------------------------------------------------------------------
// Roundtrip: v2 -> JSON -> upgradeWorkflowSpec (passthrough)
// ---------------------------------------------------------------------------

describe('Roundtrip: upgradeWorkflowSpec passthrough', () => {
  it('v2 spec passes through upgradeWorkflowSpec unchanged after JSON roundtrip', () => {
    const wf = makeComplexV2Spec()
    const roundtripped = jsonRoundtrip<WorkflowSpecV2>(wf)
    const upgraded = upgradeWorkflowSpec(roundtripped)

    // upgradeWorkflowSpec returns the same reference for v2
    expect(upgraded).toBe(roundtripped)
    expect(upgraded.schemaVersion).toBe('2.0')
    expect(upgraded.nodes).toHaveLength(3)
    expect(upgraded.edges).toHaveLength(2)
  })
})

// ---------------------------------------------------------------------------
// Roundtrip: Import/export preserves all fields
// ---------------------------------------------------------------------------

describe('Roundtrip: import/export preserves all fields', () => {
  it('export -> import (upgrade) roundtrip preserves all v2 fields', () => {
    const original = makeComplexV2Spec()

    // Simulate export: serialize to JSON (like API export endpoint)
    const exported = JSON.stringify({ spec: original })

    // Simulate import: parse and upgrade (like API import + frontend loadFromServer)
    const parsed = JSON.parse(exported)
    const imported = upgradeWorkflowSpec(parsed.spec) as WorkflowSpecV2

    expect(imported.schemaVersion).toBe('2.0')
    expect(imported.id).toBe('complex-test')
    expect(imported.name).toBe('Complex Test Workflow')
    expect(imported.description).toBe('A workflow for roundtrip testing')
    expect(imported.nodes).toHaveLength(3)
    expect(imported.edges).toHaveLength(2)
    expect(imported.viewport).toEqual({ x: -50, y: 30, zoom: 1.5 })
    expect(imported.metadata.tags).toEqual(['test', 'roundtrip'])
    expect(imported.metadata.customKey).toBe('customValue')

    // Verify node details
    const node1 = imported.nodes.find(n => n.id === 'n1')
    expect(node1!.data.config.prompt).toBe('rain city at night')
    expect(node1!.data.fieldSchema).toHaveLength(2)
    expect(node1!.data.fieldSchema![0].id).toBe('scene_count')

    // Verify edge details
    expect(imported.edges[0].sourceHandle).toBe('text')
    expect(imported.edges[0].targetHandle).toBe('prompt')
    expect(imported.edges[0].data?.mode).toBe('direct')
    expect(imported.edges[1].data?.mode).toBe('map')
    expect(imported.edges[1].data?.order).toBe(1)
  })

  it('v1 export -> import -> upgrade preserves core data', () => {
    // Simulate a v1 spec stored in DB
    const v1Spec: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'v1-export',
      name: 'V1 Exported Workflow',
      nodes: [makeNode('n1', 'textInput'), makeNode('n2', 'storyboard')],
      edges: [{
        id: 'e1',
        source: 'n1',
        target: 'n2',
        type: 'smoothstep',
        data: { mode: 'direct', label: 'test-label' },
      }],
    }

    // Export (v1 stays as-is in DB)
    const exported = JSON.stringify({ spec: v1Spec })

    // Import -> upgrade
    const parsed = JSON.parse(exported)
    const imported = upgradeWorkflowSpec(parsed.spec) as WorkflowSpecV2

    expect(imported.schemaVersion).toBe('2.0')
    expect(imported.nodes).toHaveLength(2)
    expect(imported.edges[0].sourceHandle).toBe('text')
    expect(imported.edges[0].targetHandle).toBe('prompt')
    expect(imported.edges[0].data?.mode).toBe('direct')
    expect(imported.edges[0].data?.label).toBe('test-label')
    expect(imported.viewport).toEqual({ x: 0, y: 0, zoom: 1 })
  })
})

// ---------------------------------------------------------------------------
// Roundtrip: DB persistence preserves all fields
// (simulates: frontend v2 -> API -> backend JSON -> DB -> backend JSON -> frontend v2)
// ---------------------------------------------------------------------------

describe('Roundtrip: DB persistence (simulated)', () => {
  it('v2 workflow survives full serialize-store-load-deserialize cycle', () => {
    const original = makeComplexV2Spec()

    // Simulate: frontend sends spec as JSON to API -> backend stores as spec_json
    const specJson = JSON.stringify(original)

    // Simulate: backend reads spec_json, parses it (get_workflow)
    const fromDb = JSON.parse(specJson)

    // Simulate: frontend loads from API and upgrades
    const loaded = upgradeWorkflowSpec(fromDb) as WorkflowSpecV2

    // Verify full fidelity
    expect(loaded.schemaVersion).toBe('2.0')
    expect(loaded.manifestVersion).toBe('1.0')
    expect(loaded.id).toBe(original.id)
    expect(loaded.name).toBe(original.name)
    expect(loaded.description).toBe(original.description)
    expect(loaded.viewport).toEqual(original.viewport)
    expect(loaded.metadata).toEqual(original.metadata)

    // Nodes
    expect(loaded.nodes).toHaveLength(original.nodes.length)
    for (const origNode of original.nodes) {
      const loadedNode = loaded.nodes.find(n => n.id === origNode.id)
      expect(loadedNode).toBeDefined()
      expect(loadedNode!.data.kind).toBe(origNode.data.kind)
      expect(loadedNode!.data.label).toBe(origNode.data.label)
      expect(loadedNode!.data.description).toBe(origNode.data.description)
      expect(loadedNode!.data.config).toEqual(origNode.data.config)
      expect(loadedNode!.data.fieldSchema).toEqual(origNode.data.fieldSchema)
      expect(loadedNode!.data.ports).toEqual(origNode.data.ports)
      expect(loadedNode!.position).toEqual(origNode.position)
    }

    // Edges
    expect(loaded.edges).toHaveLength(original.edges.length)
    for (let i = 0; i < original.edges.length; i++) {
      expect(loaded.edges[i].sourceHandle).toBe(original.edges[i].sourceHandle)
      expect(loaded.edges[i].targetHandle).toBe(original.edges[i].targetHandle)
      expect(loaded.edges[i].data?.mode).toBe(original.edges[i].data?.mode)
      expect(loaded.edges[i].data?.label).toBe(original.edges[i].data?.label)
      expect(loaded.edges[i].data?.sourcePath).toBe(original.edges[i].data?.sourcePath)
      expect(loaded.edges[i].data?.targetPath).toBe(original.edges[i].data?.targetPath)
      expect(loaded.edges[i].data?.order).toBe(original.edges[i].data?.order)
    }
  })

  it('v2 update roundtrip preserves version progression', () => {
    const original = makeComplexV2Spec()

    // Simulate create -> update cycle
    const specV1 = JSON.parse(JSON.stringify(original))
    // mutate name
    specV1.name = 'Updated Name'
    const specV2 = JSON.parse(JSON.stringify(specV1))

    const loaded = upgradeWorkflowSpec(specV2) as WorkflowSpecV2
    expect(loaded.name).toBe('Updated Name')
    expect(loaded.id).toBe('complex-test')
    // All other fields preserved
    expect(loaded.nodes).toHaveLength(3)
    expect(loaded.edges).toHaveLength(2)
  })
})

// ---------------------------------------------------------------------------
// Roundtrip: WorkflowSpec (union type) with v2 data
// ---------------------------------------------------------------------------

describe('Roundtrip: WorkflowSpec union type', () => {
  it('v2 spec as WorkflowSpec preserves schemaVersion through JSON roundtrip', () => {
    const original: WorkflowSpec = {
      schemaVersion: '2.0',
      manifestVersion: '1.0',
      id: 'union-test',
      name: 'Union Test',
      nodes: [makeNode('n1', 'textInput')],
      edges: [],
      viewport: { x: 10, y: 20, zoom: 0.8 },
      metadata: { tags: ['union'] },
    }

    const roundtripped = jsonRoundtrip<WorkflowSpec>(original)
    expect(roundtripped.schemaVersion).toBe('2.0')
    expect(roundtripped.viewport).toEqual({ x: 10, y: 20, zoom: 0.8 })
    expect(roundtripped.metadata).toEqual({ tags: ['union'] })
  })
})

// ---------------------------------------------------------------------------
// v1 -> v2 migration verification
// ---------------------------------------------------------------------------

describe('Migration: v1 -> v2 comprehensive verification', () => {
  it('v1 workflow without viewport opens correctly after migration', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'legacy-wf',
      name: 'Legacy Workflow',
      nodes: [
        makeNode('n1', 'textInput'),
        makeNode('n2', 'storyboard'),
        makeNode('n3', 'textToImage'),
        makeNode('n4', 'imageToVideo'),
        makeNode('n5', 'videoConcat'),
        makeNode('n6', 'output'),
      ],
      edges: [
        { id: 'e1', source: 'n1', target: 'n2', type: 'smoothstep' },
        { id: 'e2', source: 'n2', target: 'n3', type: 'smoothstep' },
        { id: 'e3', source: 'n3', target: 'n4', type: 'smoothstep' },
        { id: 'e4', source: 'n4', target: 'n5', type: 'smoothstep' },
        { id: 'e5', source: 'n5', target: 'n6', type: 'smoothstep' },
      ],
    }

    const v2 = upgradeWorkflowSpec(v1)

    // Schema version upgraded
    expect(v2.schemaVersion).toBe('2.0')
    expect(v2.manifestVersion).toBe('1.0')
    expect(v2.id).toBe('legacy-wf')
    expect(v2.name).toBe('Legacy Workflow')

    // Viewport defaults to {x:0, y:0, zoom:1}
    expect(v2.viewport).toEqual({ x: 0, y: 0, zoom: 1 })

    // Metadata has sensible defaults
    expect(v2.metadata.tags).toEqual([])
    expect(v2.metadata.createdAt).toBeDefined()

    // All 6 nodes preserved
    expect(v2.nodes).toHaveLength(6)
    expect(v2.nodes[0].data.kind).toBe('textInput')
    expect(v2.nodes[5].data.kind).toBe('output')

    // All 5 edges preserved with handles
    expect(v2.edges).toHaveLength(5)
  })

  it('v1 edges get default handles from NODE_CATALOG (textInput -> storyboard)', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'handle-test',
      name: 'Handle Test',
      nodes: [makeNode('n1', 'textInput'), makeNode('n2', 'storyboard')],
      edges: [{ id: 'e1', source: 'n1', target: 'n2', type: 'smoothstep' }],
    }

    const v2 = migrateV1toV2(v1)

    // textInput outputs "text", storyboard inputs "prompt"
    expect(v2.edges[0].sourceHandle).toBe(NODE_CATALOG.textInput.ports.outputs[0].id)
    expect(v2.edges[0].targetHandle).toBe(NODE_CATALOG.storyboard.ports.inputs[0].id)
  })

  it('v1 edges get correct handles for all node pairs', () => {
    const pairs: Array<[import('../types').NodeKind, import('../types').NodeKind, string, string]> = [
      ['textInput', 'storyboard', 'text', 'prompt'],
      ['storyboard', 'textToImage', 'scenes', 'scene'],
      ['textToImage', 'imageToVideo', 'image', 'image'],
      ['imageToVideo', 'videoConcat', 'video', 'video'],
      ['videoConcat', 'output', 'video', 'video'],
    ]

    for (const [sourceKind, targetKind, expectedSource, expectedTarget] of pairs) {
      const v1: WorkflowSpecV1 = {
        schemaVersion: '1.0',
        id: 'test',
        name: 'Test',
        nodes: [makeNode('n1', sourceKind), makeNode('n2', targetKind)],
        edges: [{ id: 'e1', source: 'n1', target: 'n2', type: 'smoothstep' }],
      }

      const v2 = migrateV1toV2(v1)
      expect(v2.edges[0].sourceHandle).toBe(expectedSource)
      expect(v2.edges[0].targetHandle).toBe(expectedTarget)
    }
  })

  it('v1 viewport defaults to {x:0, y:0, zoom:1}', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [],
      edges: [],
    }

    const v2 = migrateV1toV2(v1)
    expect(v2.viewport).toEqual({ x: 0, y: 0, zoom: 1 })
  })

  it('v1 no data loss: positions, config, label, description, kind preserved', () => {
    const node: StudioNode = {
      id: 'n1',
      type: 'studio',
      position: { x: 123, y: 456 },
      data: {
        label: 'My Custom Label',
        description: 'Custom description',
        kind: 'imageToVideo',
        status: 'idle',
        config: { resolution: '720P', ratio: '16:9', duration: 10, audio: false },
      },
    }

    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [node],
      edges: [],
    }

    const v2 = migrateV1toV2(v1)

    expect(v2.nodes[0].id).toBe('n1')
    expect(v2.nodes[0].position).toEqual({ x: 123, y: 456 })
    expect(v2.nodes[0].data.label).toBe('My Custom Label')
    expect(v2.nodes[0].data.description).toBe('Custom description')
    expect(v2.nodes[0].data.kind).toBe('imageToVideo')
    expect(v2.nodes[0].data.config.resolution).toBe('720P')
    expect(v2.nodes[0].data.config.ratio).toBe('16:9')
    expect(v2.nodes[0].data.config.duration).toBe(10)
    expect(v2.nodes[0].data.config.audio).toBe(false)
  })

  it('v1 edge data preserved through migration', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [makeNode('n1', 'textInput'), makeNode('n2', 'storyboard')],
      edges: [{
        id: 'e1',
        source: 'n1',
        sourceHandle: 'text',
        target: 'n2',
        targetHandle: 'prompt',
        type: 'smoothstep',
        data: { mode: 'map', label: 'my-edge', order: 3, sourcePath: '$.x', targetPath: '$.y' },
      }],
    }

    const v2 = migrateV1toV2(v1)
    expect(v2.edges[0].sourceHandle).toBe('text')
    expect(v2.edges[0].targetHandle).toBe('prompt')
    expect(v2.edges[0].data?.mode).toBe('map')
    expect(v2.edges[0].data?.label).toBe('my-edge')
    expect(v2.edges[0].data?.order).toBe(3)
    expect(v2.edges[0].data?.sourcePath).toBe('$.x')
    expect(v2.edges[0].data?.targetPath).toBe('$.y')
  })

  it('v1 missing schemaVersion treated as v1 and migrates correctly', () => {
    const spec = {
      id: 'no-version',
      name: 'No Version Spec',
      nodes: [makeNode('n1', 'textInput'), makeNode('n2', 'storyboard')],
      edges: [{ id: 'e1', source: 'n1', target: 'n2', type: 'smoothstep' }],
    }

    const v2 = upgradeWorkflowSpec(spec)
    expect(v2.schemaVersion).toBe('2.0')
    expect(v2.viewport).toEqual({ x: 0, y: 0, zoom: 1 })
    expect(v2.edges[0].sourceHandle).toBe('text')
    expect(v2.edges[0].targetHandle).toBe('prompt')
  })

  it('v1 fieldSchema preserved through v1->v2 migration', () => {
    const node = makeNode('n1', 'textInput')
    node.data.fieldSchema = [
      { id: 'my_text', label: 'My Text', type: 'text', required: true },
      { id: 'my_num', label: 'My Number', type: 'number', default: 10 },
    ]
    node.data.config = { my_text: 'hello', my_num: 10 }

    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'test',
      name: 'Test',
      nodes: [node],
      edges: [],
    }

    const v2 = migrateV1toV2(v1)
    expect(v2.nodes[0].data.fieldSchema).toHaveLength(2)
    expect(v2.nodes[0].data.fieldSchema![0].id).toBe('my_text')
    expect(v2.nodes[0].data.fieldSchema![0].required).toBe(true)
    expect(v2.nodes[0].data.fieldSchema![1].id).toBe('my_num')
    expect(v2.nodes[0].data.fieldSchema![1].default).toBe(10)
    expect(v2.nodes[0].data.config.my_text).toBe('hello')
    expect(v2.nodes[0].data.config.my_num).toBe(10)
  })

  it('v1 full workflow migration then JSON roundtrip preserves everything', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'full-migration',
      name: 'Full Migration Test',
      nodes: [
        { ...makeNode('n1', 'textInput'), position: { x: 100, y: 200 }, data: { ...makeNode('n1', 'textInput').data, config: { prompt: 'test prompt' } } },
        { ...makeNode('n2', 'storyboard'), data: { ...makeNode('n2', 'storyboard').data, config: { scenes: 3, style: 'cinematic' } } },
      ],
      edges: [{
        id: 'e1',
        source: 'n1',
        target: 'n2',
        type: 'smoothstep',
        data: { mode: 'direct' },
      }],
    }

    // Migrate v1 -> v2
    const v2 = migrateV1toV2(v1)

    // JSON roundtrip
    const roundtripped = jsonRoundtrip<WorkflowSpecV2>(v2)

    // Verify all preserved
    expect(roundtripped.schemaVersion).toBe('2.0')
    expect(roundtripped.nodes).toHaveLength(2)
    expect(roundtripped.nodes[0].position).toEqual({ x: 100, y: 200 })
    expect(roundtripped.nodes[0].data.config.prompt).toBe('test prompt')
    expect(roundtripped.nodes[1].data.config.scenes).toBe(3)
    expect(roundtripped.nodes[1].data.config.style).toBe('cinematic')
    expect(roundtripped.edges[0].sourceHandle).toBe('text')
    expect(roundtripped.edges[0].targetHandle).toBe('prompt')
    expect(roundtripped.edges[0].data?.mode).toBe('direct')
    expect(roundtripped.viewport).toEqual({ x: 0, y: 0, zoom: 1 })
    expect(roundtripped.metadata).toBeDefined()
  })
})

// ---------------------------------------------------------------------------
// v2 -> v1 -> v2 roundtrip
// ---------------------------------------------------------------------------

describe('Roundtrip: v2 -> v1 -> v2 (downgrade + upgrade)', () => {
  it('preserves core node data through downgrade/upgrade cycle', () => {
    const original = makeComplexV2Spec()

    // v2 -> v1
    const v1 = downgradeWorkflowSpec(original)
    expect(v1.schemaVersion).toBe('1.0')

    // v1 -> v2
    const restored = upgradeWorkflowSpec(v1) as WorkflowSpecV2
    expect(restored.schemaVersion).toBe('2.0')

    // Nodes
    expect(restored.nodes).toHaveLength(original.nodes.length)
    for (let i = 0; i < original.nodes.length; i++) {
      expect(restored.nodes[i].id).toBe(original.nodes[i].id)
      expect(restored.nodes[i].data.kind).toBe(original.nodes[i].data.kind)
      expect(restored.nodes[i].data.label).toBe(original.nodes[i].data.label)
      expect(restored.nodes[i].data.description).toBe(original.nodes[i].data.description)
      expect(restored.nodes[i].data.config).toEqual(original.nodes[i].data.config)
      expect(restored.nodes[i].position).toEqual(original.nodes[i].position)
    }

    // fieldSchema preserved
    expect(restored.nodes[0].data.fieldSchema).toHaveLength(2)
    expect(restored.nodes[0].data.fieldSchema![0].id).toBe('scene_count')

    // Edges - handles restored from NODE_CATALOG
    expect(restored.edges).toHaveLength(original.edges.length)
    for (let i = 0; i < original.edges.length; i++) {
      expect(restored.edges[i].source).toBe(original.edges[i].source)
      expect(restored.edges[i].target).toBe(original.edges[i].target)
      // sourceHandle/targetHandle should be re-populated by migration
      expect(restored.edges[i].sourceHandle).toBeDefined()
      expect(restored.edges[i].targetHandle).toBeDefined()
    }
  })

  it('v2 -> v1 strips handles and ports, v2 re-adds them', () => {
    const v2 = makeComplexV2Spec()

    const v1 = downgradeWorkflowSpec(v2)

    // v1 edges have no handles
    for (const edge of v1.edges) {
      expect(edge.sourceHandle).toBeUndefined()
      expect(edge.targetHandle).toBeUndefined()
    }

    // v1 nodes have no ports
    for (const node of v1.nodes) {
      expect(node.data.ports).toBeUndefined()
    }

    // Upgrade back
    const restored = upgradeWorkflowSpec(v1) as WorkflowSpecV2

    // Handles restored
    expect(restored.edges[0].sourceHandle).toBe('text')
    expect(restored.edges[0].targetHandle).toBe('prompt')
    expect(restored.edges[1].sourceHandle).toBe('scenes')
    expect(restored.edges[1].targetHandle).toBe('scene')

    // Ports restored
    expect(restored.nodes[0].data.ports).toBeDefined()
    expect(restored.nodes[0].data.ports!.outputs).toHaveLength(1)
  })

  it('fieldSchema and config survive v2 -> v1 -> v2', () => {
    const node = makeNode('n1', 'textInput')
    node.data.fieldSchema = [
      { id: 'custom', label: 'Custom', type: 'text', default: 'hello', required: true },
    ]
    node.data.config = { custom: 'world' }

    const v2: WorkflowSpecV2 = {
      schemaVersion: '2.0',
      manifestVersion: '1.0',
      id: 'field-test',
      name: 'Field Test',
      nodes: [node],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      metadata: { tags: [] },
    }

    const v1 = downgradeWorkflowSpec(v2)
    const restored = upgradeWorkflowSpec(v1) as WorkflowSpecV2

    expect(restored.nodes[0].data.fieldSchema).toHaveLength(1)
    expect(restored.nodes[0].data.fieldSchema![0].id).toBe('custom')
    expect(restored.nodes[0].data.fieldSchema![0].default).toBe('hello')
    expect(restored.nodes[0].data.fieldSchema![0].required).toBe(true)
    expect(restored.nodes[0].data.config.custom).toBe('world')
  })
})
