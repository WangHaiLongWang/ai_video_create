import type { Edge } from '@xyflow/react'
import type { NodeKind } from '../types'
import type { NodeManifest, PortDefinition, PortType } from './node-manifest'
import { NODE_CATALOG } from './node-manifest'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface ValidationError {
  code: string       // e.g. "SELF_LOOP", "DUPLICATE_EDGE", "TYPE_MISMATCH", ...
  message: string    // human-readable Chinese message
  edgeId?: string
  nodeId?: string
  portId?: string
}

interface NodeRecord {
  id: string
  kind?: NodeKind
  data?: { kind?: NodeKind }
}

interface EdgeRecord {
  id: string
  source: string
  sourceHandle?: string | null
  target: string
  targetHandle?: string | null
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Extract NodeKind from either top-level `kind` or nested `data.kind`. */
function nodeKind(node: NodeRecord): NodeKind | undefined {
  return node.kind ?? node.data?.kind
}

function findOutputPort(manifest: NodeManifest, handleId: string | null | undefined): PortDefinition | undefined {
  return manifest.ports.outputs.find((p) => p.id === handleId)
}

function findInputPort(manifest: NodeManifest, handleId: string | null | undefined): PortDefinition | undefined {
  return manifest.ports.inputs.find((p) => p.id === handleId)
}

/** Two types are compatible when they are identical or either side is "any". */
function typesCompatible(a: PortType, b: PortType): boolean {
  return a === b || a === 'any' || b === 'any'
}

// ---------------------------------------------------------------------------
// Full graph validation
// ---------------------------------------------------------------------------
export function validateGraph(
  nodes: NodeRecord[],
  edges: EdgeRecord[],
  catalog: Record<string, NodeManifest> = NODE_CATALOG,
): ValidationError[] {
  const errors: ValidationError[] = []
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))

  // 1. Self-loop
  for (const edge of edges) {
    if (edge.source === edge.target) {
      errors.push({
        code: 'SELF_LOOP',
        message: `连线 ${edge.id} 不能连接节点自身`,
        edgeId: edge.id,
      })
    }
  }

  // 2. Duplicate edge (same source+sourceHandle -> target+targetHandle)
  const edgeKeySet = new Set<string>()
  for (const edge of edges) {
    const key = `${edge.source}::${edge.sourceHandle ?? ''}>>${edge.target}::${edge.targetHandle ?? ''}`
    if (edgeKeySet.has(key)) {
      errors.push({
        code: 'DUPLICATE_EDGE',
        message: `连线 ${edge.id} 重复：相同的源端口已连接到相同的目标端口`,
        edgeId: edge.id,
      })
    }
    edgeKeySet.add(key)
  }

  // 3. Type mismatch
  for (const edge of edges) {
    const srcNode = nodeMap.get(edge.source)
    const tgtNode = nodeMap.get(edge.target)
    if (!srcNode || !tgtNode) continue

    const srcManifest = catalog[nodeKind(srcNode) ?? '']
    const tgtManifest = catalog[nodeKind(tgtNode) ?? '']
    if (!srcManifest || !tgtManifest) continue

    const srcPort = findOutputPort(srcManifest, edge.sourceHandle)
    const tgtPort = findInputPort(tgtManifest, edge.targetHandle)

    if (srcPort && tgtPort && !typesCompatible(srcPort.type, tgtPort.type)) {
      errors.push({
        code: 'TYPE_MISMATCH',
        message: `端口类型不兼容：${srcNode.id} 的 ${srcPort.type} 不能连接到 ${tgtNode.id} 的 ${tgtPort.type}`,
        edgeId: edge.id,
        nodeId: edge.target,
        portId: tgtPort.id,
      })
    }
  }

  // 4. Cardinality violation — "one" input already has an edge
  const inputEdgeCount = new Map<string, number>()
  for (const edge of edges) {
    const key = `${edge.target}::${edge.targetHandle ?? ''}`
    inputEdgeCount.set(key, (inputEdgeCount.get(key) ?? 0) + 1)
  }
  for (const [key, count] of inputEdgeCount) {
    if (count <= 1) continue
    const [nodeId, portHandle] = key.split('::')
    const node = nodeMap.get(nodeId)
    if (!node) continue
    const manifest = catalog[nodeKind(node) ?? '']
    if (!manifest) continue
    const port = findInputPort(manifest, portHandle)
    if (port && port.cardinality === 'one' && count > 1) {
      errors.push({
        code: 'CARDINALITY_VIOLATION',
        message: `端口 ${port.id} 的基数为 "one"，但已连接 ${count} 条边`,
        nodeId,
        portId: port.id,
      })
    }
  }

  // 5. Required port warning — required input with no edge
  for (const node of nodes) {
    const manifest = catalog[nodeKind(node) ?? '']
    if (!manifest) continue
    for (const port of manifest.ports.inputs) {
      if (!port.required) continue
      const hasEdge = edges.some(
        (e) => e.target === node.id && (e.targetHandle ?? '') === port.id,
      )
      if (!hasEdge) {
        errors.push({
          code: 'REQUIRED_PORT',
          message: `节点 ${node.id} 的必需输入端口 ${port.id} 未连接`,
          nodeId: node.id,
          portId: port.id,
        })
      }
    }
  }

  // 6. Cycle detection — DFS on the directed graph
  const adjacency = new Map<string, string[]>()
  for (const node of nodes) {
    adjacency.set(node.id, [])
  }
  for (const edge of edges) {
    const list = adjacency.get(edge.source)
    if (list) list.push(edge.target)
  }

  const WHITE = 0, GRAY = 1, BLACK = 2
  const color = new Map<string, number>()
  for (const node of nodes) color.set(node.id, WHITE)

  let hasCycle = false
  let cycleEdgeId: string | undefined

  function dfs(u: string): void {
    if (hasCycle) return
    color.set(u, GRAY)
    for (const v of adjacency.get(u) ?? []) {
      if (hasCycle) return
      if (color.get(v) === GRAY) {
        // Found cycle — find the edge that closes it
        const cycleEdge = edges.find((e) => e.source === u && e.target === v)
        cycleEdgeId = cycleEdge?.id
        hasCycle = true
        return
      }
      if (color.get(v) === WHITE) {
        dfs(v)
      }
    }
    color.set(u, BLACK)
  }

  for (const node of nodes) {
    if (color.get(node.id) === WHITE) {
      dfs(node.id)
      if (hasCycle) break
    }
  }

  if (hasCycle) {
    errors.push({
      code: 'CYCLE',
      message: '图中存在环路，工作流不能包含循环',
      edgeId: cycleEdgeId,
    })
  }

  // 7. Direction — output→output or input→input
  for (const edge of edges) {
    const srcNode = nodeMap.get(edge.source)
    const tgtNode = nodeMap.get(edge.target)
    if (!srcNode || !tgtNode) continue

    const srcManifest = catalog[nodeKind(srcNode) ?? '']
    const tgtManifest = catalog[nodeKind(tgtNode) ?? '']
    if (!srcManifest || !tgtManifest) continue

    const srcPort = findOutputPort(srcManifest, edge.sourceHandle)
    const tgtPort = findInputPort(tgtManifest, edge.targetHandle)

    // If source handle is an input port or target handle is an output port
    if (!srcPort && findInputPort(srcManifest, edge.sourceHandle)) {
      errors.push({
        code: 'DIRECTION',
        message: `连线 ${edge.id} 不能从输入端口 ${edge.sourceHandle ?? ''} 发出`,
        edgeId: edge.id,
      })
    }
    if (!tgtPort && findOutputPort(tgtManifest, edge.targetHandle)) {
      errors.push({
        code: 'DIRECTION',
        message: `连线 ${edge.id} 不能连接到输出端口 ${edge.targetHandle ?? ''}`,
        edgeId: edge.id,
      })
    }
  }

  return errors
}

// ---------------------------------------------------------------------------
// Single connection validation
// ---------------------------------------------------------------------------

/**
 * Validate a single connection attempt before committing it.
 *
 * @param source        Source node ID
 * @param sourceHandle  Source port (handle) ID
 * @param target        Target node ID
 * @param targetHandle  Target port (handle) ID
 * @param nodeKinds     Mapping of node ID to its NodeKind
 * @param catalog       Node manifest catalog (defaults to NODE_CATALOG)
 * @param existingEdges Current edges in the graph
 * @returns null if valid, or a single ValidationError
 */
export function validateConnection(
  source: string,
  sourceHandle: string | undefined,
  target: string,
  targetHandle: string | undefined,
  nodeKinds: Record<string, NodeKind> = {},
  catalog: Record<string, NodeManifest> = NODE_CATALOG,
  existingEdges: EdgeRecord[] = [],
): ValidationError | null {
  // Resolve source and target manifests via their NodeKind
  const srcKind = nodeKinds[source]
  const tgtKind = nodeKinds[target]
  const srcManifest = srcKind ? catalog[srcKind] : undefined
  const tgtManifest = tgtKind ? catalog[tgtKind] : undefined

  // Self-loop
  if (source === target) {
    return {
      code: 'SELF_LOOP',
      message: '连线不能连接节点自身',
    }
  }

  // Duplicate edge
  const key = `${source}::${sourceHandle ?? ''}>>${target}::${targetHandle ?? ''}`
  const isDuplicate = existingEdges.some((e) => {
    const ek = `${e.source}::${e.sourceHandle ?? ''}>>${e.target}::${e.targetHandle ?? ''}`
    return ek === key
  })
  if (isDuplicate) {
    return {
      code: 'DUPLICATE_EDGE',
      message: '相同的连接已存在',
    }
  }

  if (srcManifest && tgtManifest) {
    const srcOutputPort = findOutputPort(srcManifest, sourceHandle)
    const srcInputPort = findInputPort(srcManifest, sourceHandle)
    const tgtOutputPort = findOutputPort(tgtManifest, targetHandle)
    const tgtInputPort = findInputPort(tgtManifest, targetHandle)

    // Direction — can't connect from an input port or into an output port
    if (!srcOutputPort && srcInputPort) {
      return {
        code: 'DIRECTION',
        message: `不能从输入端口 ${sourceHandle ?? ''} 发出连线`,
        portId: sourceHandle,
      }
    }

    if (!tgtInputPort && tgtOutputPort) {
      return {
        code: 'DIRECTION',
        message: `不能连接到输出端口 ${targetHandle ?? ''}`,
        portId: targetHandle,
      }
    }

    // Type mismatch
    if (srcOutputPort && tgtInputPort) {
      if (!typesCompatible(srcOutputPort.type, tgtInputPort.type)) {
        return {
          code: 'TYPE_MISMATCH',
          message: `端口类型不兼容：${srcOutputPort.type} 不能连接到 ${tgtInputPort.type}`,
          portId: targetHandle,
        }
      }
    }

    // Cardinality violation
    if (tgtInputPort && tgtInputPort.cardinality === 'one') {
      const existingCount = existingEdges.filter(
        (e) => e.target === target && (e.targetHandle ?? '') === (targetHandle ?? ''),
      ).length
      if (existingCount >= 1) {
        return {
          code: 'CARDINALITY_VIOLATION',
          message: `端口 ${tgtInputPort.id} 的基数为 "one"，已连接 ${existingCount} 条边`,
          portId: targetHandle,
        }
      }
    }
  }

  return null
}
