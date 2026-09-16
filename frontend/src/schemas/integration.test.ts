/**
 * integration.test — End-to-end WorkflowSpec 2.0 flow
 *
 * Tests:
 * 1. Create workflow with createPromptToVideoWorkflow → validate → no errors
 * 2. Add a node, connect → validation passes
 * 3. Create invalid connection → validation rejects
 * 4. Export to JSON → valid v2 format
 * 5. Parse back → same structure (roundtrip)
 * 6. Migrate v1 spec → v2 → validate → no errors
 */

import { describe, it, expect } from 'vitest'
import { createPromptToVideoWorkflow, createNode } from '../workflow'
import { validateGraph, validateConnection } from './graph-validation'
import { upgradeWorkflowSpec, migrateV1toV2, type WorkflowSpecV1 } from './workflow-spec'
import { NODE_CATALOG } from './node-manifest'
import type { NodeKind } from '../types'

// ---------------------------------------------------------------------------
// 1. Default workflow validates cleanly
// ---------------------------------------------------------------------------
describe('integration — default workflow', () => {
  it('createPromptToVideoWorkflow produces a valid graph', () => {
    const wf = createPromptToVideoWorkflow()
    const errors = validateGraph(wf.nodes, wf.edges, NODE_CATALOG)
    const realErrors = errors.filter(e => e.code !== 'REQUIRED_PORT')
    expect(realErrors).toHaveLength(0)
  })
})

// ---------------------------------------------------------------------------
// 2. Add a node, connect → validation passes
// ---------------------------------------------------------------------------
describe('integration — add node and connect', () => {
  it('adding a second videoConcat and connecting its output to a new output node is valid', () => {
    const wf = createPromptToVideoWorkflow()
    // Add a second videoConcat (many→one input) and an output node
    const extraConcat = createNode('videoConcat', 500, 300, 'extra-concat')
    const extraOutput = createNode('output', 700, 300, 'extra-output')
    const nodes = [...wf.nodes, extraConcat, extraOutput]

    // Validate the graph with no extra edges — just the nodes
    const errors = validateGraph(nodes, wf.edges, NODE_CATALOG)
    const realErrors = errors.filter(e => e.code !== 'REQUIRED_PORT')
    expect(realErrors).toHaveLength(0)

    // Now validate a new connection: extraConcat.video → extraOutput.video
    const nodeKinds: Record<string, NodeKind> = {}
    nodes.forEach(n => { nodeKinds[n.id] = n.data.kind })

    const connError = validateConnection(
      'extra-concat', 'video',
      'extra-output', 'video',
      nodeKinds, NODE_CATALOG, wf.edges,
    )
    expect(connError).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// 3. Invalid connection → rejected
// ---------------------------------------------------------------------------
describe('integration — invalid connection', () => {
  it('type mismatch is rejected by validateConnection', () => {
    const wf = createPromptToVideoWorkflow()
    const nodeKinds: Record<string, NodeKind> = {}
    wf.nodes.forEach(n => { nodeKinds[n.id] = n.data.kind })

    // Try to connect videoConcat output (video) → textToImage input (scene)
    const error = validateConnection(
      'videoConcat-1', 'video',
      'textToImage-1', 'scene',
      nodeKinds, NODE_CATALOG, wf.edges,
    )
    expect(error).not.toBeNull()
    expect(error!.code).toBe('TYPE_MISMATCH')
  })

  it('self-loop is rejected by validateGraph', () => {
    const wf = createPromptToVideoWorkflow()
    // Add a self-loop edge
    const selfLoopEdge = {
      id: 'self-loop',
      source: 'storyboard-1',
      sourceHandle: 'scenes',
      target: 'storyboard-1',
      targetHandle: 'prompt',
      type: 'smoothstep' as const,
      data: { mode: 'direct' as const, label: '' },
    }
    const edges = [...wf.edges, selfLoopEdge]
    const errors = validateGraph(wf.nodes, edges, NODE_CATALOG)
    expect(errors.some(e => e.code === 'SELF_LOOP')).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// 4. Export to JSON → valid v2 format
// ---------------------------------------------------------------------------
describe('integration — JSON export', () => {
  it('serialized workflow is valid v2 format', () => {
    const wf = createPromptToVideoWorkflow()
    const json = JSON.stringify(wf)
    const parsed = JSON.parse(json)

    expect(parsed.schemaVersion).toBe('2.0')
    expect(parsed.manifestVersion).toBe('1.0')
    expect(parsed.viewport).toBeDefined()
    expect(parsed.metadata).toBeDefined()
    expect(Array.isArray(parsed.nodes)).toBe(true)
    expect(Array.isArray(parsed.edges)).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// 5. Roundtrip — parse back → same structure
// ---------------------------------------------------------------------------
describe('integration — roundtrip', () => {
  it('JSON.parse(JSON.stringify(wf)) preserves structure', () => {
    const wf = createPromptToVideoWorkflow('roundtrip test')
    const json = JSON.stringify(wf)
    const parsed = JSON.parse(json)

    expect(parsed.schemaVersion).toBe('2.0')
    expect(parsed.id).toBe(wf.id)
    expect(parsed.name).toBe(wf.name)
    expect(parsed.nodes).toHaveLength(wf.nodes.length)
    expect(parsed.edges).toHaveLength(wf.edges.length)

    // Verify edges have handles
    for (let i = 0; i < parsed.edges.length; i++) {
      expect(parsed.edges[i].sourceHandle).toBe(wf.edges[i].sourceHandle)
      expect(parsed.edges[i].targetHandle).toBe(wf.edges[i].targetHandle)
    }

    // Verify nodes have ports
    for (let i = 0; i < parsed.nodes.length; i++) {
      expect(parsed.nodes[i].data.ports).toBeDefined()
    }
  })
})

// ---------------------------------------------------------------------------
// 6. Migrate v1 → v2 → validate
// ---------------------------------------------------------------------------
describe('integration — v1 migration', () => {
  it('migrated v1 spec validates cleanly', () => {
    const v1: WorkflowSpecV1 = {
      schemaVersion: '1.0',
      id: 'migrated',
      name: 'Migrated',
      nodes: [
        { id: 'n1', type: 'studio', position: { x: 0, y: 0 }, data: { label: 'Input', description: '', kind: 'textInput', status: 'idle', config: {} } },
        { id: 'n2', type: 'studio', position: { x: 200, y: 0 }, data: { label: 'Storyboard', description: '', kind: 'storyboard', status: 'idle', config: {} } },
      ],
      edges: [{
        id: 'e1',
        source: 'n1',
        target: 'n2',
        type: 'smoothstep',
      }],
    }

    const v2 = migrateV1toV2(v1)
    expect(v2.schemaVersion).toBe('2.0')

    // Validate migrated graph
    const errors = validateGraph(v2.nodes, v2.edges, NODE_CATALOG)
    const realErrors = errors.filter(e => e.code !== 'REQUIRED_PORT')
    expect(realErrors).toHaveLength(0)
  })

  it('upgradeWorkflowSpec then validate: text→video is type mismatch', () => {
    const raw = {
      id: 'auto',
      name: 'Auto',
      nodes: [
        { id: 'n1', type: 'studio', position: { x: 0, y: 0 }, data: { label: 'Input', description: '', kind: 'textInput' as const, status: 'idle' as const, config: {} } },
        { id: 'n2', type: 'studio', position: { x: 200, y: 0 }, data: { label: 'Output', description: '', kind: 'output' as const, status: 'idle' as const, config: {} } },
      ],
      edges: [{
        id: 'e1',
        source: 'n1',
        sourceHandle: 'text',
        target: 'n2',
        targetHandle: 'video',
        type: 'smoothstep',
      }],
    }

    const v2 = upgradeWorkflowSpec(raw)
    expect(v2.schemaVersion).toBe('2.0')

    // validateGraph expects {id, kind} at top level; extract from data.kind
    const flatNodes = v2.nodes.map(n => ({ id: n.id, kind: n.data.kind }))
    const errors = validateGraph(flatNodes, v2.edges, NODE_CATALOG)
    expect(errors.some(e => e.code === 'TYPE_MISMATCH')).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// 7. Full pipeline roundtrip
// ---------------------------------------------------------------------------
describe('integration — full pipeline roundtrip', () => {
  it('create → export → import → upgrade → validate', () => {
    // Create
    const original = createPromptToVideoWorkflow()

    // Export
    const json = JSON.stringify(original)

    // Import (simulate as v1 by stripping v2 fields)
    const parsed = JSON.parse(json)
    delete parsed.schemaVersion
    delete parsed.manifestVersion
    delete parsed.viewport
    delete parsed.metadata

    // Upgrade
    const restored = upgradeWorkflowSpec(parsed)

    // Validate
    expect(restored.schemaVersion).toBe('2.0')
    expect(restored.nodes).toHaveLength(6)
    expect(restored.edges).toHaveLength(5)

    const errors = validateGraph(restored.nodes, restored.edges, NODE_CATALOG)
    const realErrors = errors.filter(e => e.code !== 'REQUIRED_PORT')
    expect(realErrors).toHaveLength(0)
  })
})
