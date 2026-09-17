import type { EnhancedEdge, StudioNode, StudioNodeData, EdgeData } from '../types'
import { NODE_CATALOG } from './node-manifest'

// ---------------------------------------------------------------------------
// V2 spec types
// ---------------------------------------------------------------------------

export interface WorkflowSpecV2 {
  schemaVersion: '2.0'
  manifestVersion: '1.0'
  id: string
  name: string
  description?: string
  nodes: StudioNode[]
  edges: EnhancedEdge[]
  viewport: { x: number; y: number; zoom: number }
  metadata: {
    tags?: string[]
    createdBy?: string
    createdAt?: string
    updatedAt?: string
    [key: string]: unknown
  }
}

// ---------------------------------------------------------------------------
// V1 spec types (for migration)
// ---------------------------------------------------------------------------

export interface WorkflowSpecV1 {
  schemaVersion: '1.0'
  id: string
  name: string
  nodes: StudioNode[]
  edges: EnhancedEdge[]
}

// ---------------------------------------------------------------------------
// Type guards
// ---------------------------------------------------------------------------

export function isV1(spec: { schemaVersion?: string }): spec is WorkflowSpecV1 {
  return spec.schemaVersion === '1.0' || !spec.schemaVersion
}

// ---------------------------------------------------------------------------
// Migration
// ---------------------------------------------------------------------------

export function migrateV1toV2(spec: WorkflowSpecV1): WorkflowSpecV2 {
  // Migrate edges: add default sourceHandle/targetHandle if missing
  const edges = spec.edges.map(edge => {
    if (!edge.sourceHandle || !edge.targetHandle) {
      const sourceNode = spec.nodes.find(n => n.id === edge.source)
      const targetNode = spec.nodes.find(n => n.id === edge.target)
      const sourceKind = sourceNode?.data?.kind
      const targetKind = targetNode?.data?.kind
      const sourceManifest = sourceKind ? NODE_CATALOG[sourceKind] : null
      const targetManifest = targetKind ? NODE_CATALOG[targetKind] : null

      return {
        ...edge,
        sourceHandle: edge.sourceHandle ?? sourceManifest?.ports.outputs[0]?.id ?? 'out',
        targetHandle: edge.targetHandle ?? targetManifest?.ports.inputs[0]?.id ?? 'in',
        data: {
          mode: 'direct' as const,
          label: '',
          ...edge.data,
        },
      }
    }
    return { ...edge, data: { mode: 'direct' as const, label: '', ...edge.data } }
  })

  // Ensure nodes have ports populated
  const nodes = spec.nodes.map(node => {
    if (node.data.ports) return node
    const manifest = NODE_CATALOG[node.data.kind]
    if (!manifest) return node
    return {
      ...node,
      data: {
        ...node.data,
        inputType: node.data.inputType ?? manifest.ports.inputs[0]?.type,
        outputType: node.data.outputType ?? manifest.ports.outputs[0]?.type,
        ports: {
          inputs: manifest.ports.inputs.map(p => ({ id: p.id, type: p.type, required: p.required, cardinality: p.cardinality })),
          outputs: manifest.ports.outputs.map(p => ({ id: p.id, type: p.type, required: false, cardinality: p.cardinality })),
        },
      },
    }
  })

  return {
    schemaVersion: '2.0',
    manifestVersion: '1.0',
    id: spec.id,
    name: spec.name,
    nodes,
    edges,
    viewport: { x: 0, y: 0, zoom: 1 },
    metadata: { tags: [], createdAt: new Date().toISOString() },
  }
}

// ---------------------------------------------------------------------------
// Downgrade v2 → v1 (for backward compatibility / export)
// ---------------------------------------------------------------------------

export function downgradeWorkflowSpec(v2: WorkflowSpecV2): WorkflowSpecV1 {
  // Migrate edges: strip sourceHandle / targetHandle
  const edges = v2.edges.map(edge => {
    const { sourceHandle, targetHandle, ...rest } = edge
    // Clean up edge data: remove mode/label defaults if they are the default
    return rest as EnhancedEdge
  })

  // Migrate nodes: strip ports, keep inputType/outputType
  const nodes = v2.nodes.map(node => {
    const { ports, ...restData } = node.data as StudioNodeData & { ports?: unknown }
    return {
      ...node,
      data: {
        ...restData,
        inputType: node.data.inputType ?? node.data.ports?.outputs[0]?.type,
        outputType: node.data.outputType ?? node.data.ports?.inputs[0]?.type,
      },
    }
  })

  return {
    schemaVersion: '1.0',
    id: v2.id,
    name: v2.name,
    nodes,
    edges,
  }
}

// ---------------------------------------------------------------------------
// Auto-upgrade entry point
// ---------------------------------------------------------------------------

export function upgradeWorkflowSpec(spec: unknown): WorkflowSpecV2 {
  const raw = spec as Record<string, unknown>
  if (isV1(raw as { schemaVersion?: string })) {
    return migrateV1toV2(raw as unknown as WorkflowSpecV1)
  }
  return raw as unknown as WorkflowSpecV2
}
