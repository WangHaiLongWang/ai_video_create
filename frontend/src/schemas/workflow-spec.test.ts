import { describe, it, expect } from 'vitest'
import type { StudioNode, EnhancedEdge } from '../types'
import {
  isV1,
  migrateV1toV2,
  upgradeWorkflowSpec,
  type WorkflowSpecV1,
  type WorkflowSpecV2,
} from './workflow-spec'
import { createPromptToVideoWorkflow } from '../workflow'
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
