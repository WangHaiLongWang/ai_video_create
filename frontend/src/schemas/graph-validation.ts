import type { Edge } from '@xyflow/react'
import type { NodeKind, PortInfo } from '../types'
import type { NodeManifest } from './node-manifest'
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

export interface NodeDataLike {
  kind?: NodeKind
  ports?: {
    inputs: PortInfo[]
    outputs: PortInfo[]
  }
  moduleId?: string
  moduleVersion?: string
  [key: string]: unknown
}

export interface NodeRecord {
  id: string
  kind?: NodeKind
  data?: NodeDataLike
}

interface EdgeRecord {
  id: string
  source: string
  sourceHandle?: string | null
  target: string
  targetHandle?: string | null
}

/** Ports may come either as full node records or as a plain id→kind map. */
type NodeInput = NodeRecord[] | Record<string, NodeKind>

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Extract NodeKind from either top-level `kind` or nested `data.kind`. */
function nodeKind(node: NodeRecord): NodeKind | undefined {
  return node.kind ?? node.data?.kind
}

/**
 * Resolve a node's effective input/output ports.
 *
 * Prefers the per-instance `data.ports` (module extension ports, instance-level
 * port CRUD) and falls back to the kind-keyed catalog. The fallback covers
 * legacy nodes and V1 exports where `downgradeWorkflowSpec` strips ports.
 */
export function getNodeEffectivePorts(
  node: NodeRecord | undefined,
  catalog: Record<string, NodeManifest> = NODE_CATALOG,
): { inputs: PortInfo[]; outputs: PortInfo[] } {
  const instancePorts = node?.data?.ports
  if (instancePorts) {
    return {
      inputs: instancePorts.inputs ?? [],
      outputs: instancePorts.outputs ?? [],
    }
  }
  const manifest = node ? catalog[nodeKind(node) ?? ''] : undefined
  if (manifest) {
    return { inputs: manifest.ports.inputs, outputs: manifest.ports.outputs }
  }
  return { inputs: [], outputs: [] }
}

function findOutputPort(ports: PortInfo[], handleId: string | null | undefined): PortInfo | undefined {
  return ports.find((p) => p.id === handleId)
}

function findInputPort(ports: PortInfo[], handleId: string | null | undefined): PortInfo | undefined {
  return ports.find((p) => p.id === handleId)
}

/** Two types are compatible when they are identical or either side is "any". */
function typesCompatible(a: string, b: string): boolean {
  return a === b || a === 'any' || b === 'any'
}

/** Normalise the flexible node input (array or id→kind map) to an id-keyed map. */
function toNodeMap(nodes: NodeInput | undefined): Map<string, NodeRecord> {
  if (!nodes) return new Map()
  if (Array.isArray(nodes)) return new Map(nodes.map((n) => [n.id, n]))
  return new Map(Object.entries(nodes).map(([id, kind]) => [id, { id, kind }]))
}

/** True when adding source→target would close a loop over the existing edges. */
function wouldCreateCycle(
  source: string,
  target: string,
  existingEdges: EdgeRecord[],
): boolean {
  const adjacency = new Map<string, string[]>()
  for (const e of existingEdges) {
    const list = adjacency.get(e.source) ?? []
    list.push(e.target)
    adjacency.set(e.source, list)
  }
  const visited = new Set<string>()
  const stack = [target]
  while (stack.length > 0) {
    const u = stack.pop() as string
    if (u === source) return true
    if (visited.has(u)) continue
    visited.add(u)
    for (const v of adjacency.get(u) ?? []) stack.push(v)
  }
  return false
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
  // Effective ports per node: instance-level data.ports first, catalog fallback.
  const portsMap = new Map(nodes.map((n) => [n.id, getNodeEffectivePorts(n, catalog)]))

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

    const srcPorts = portsMap.get(edge.source)
    const tgtPorts = portsMap.get(edge.target)
    if (!srcPorts || !tgtPorts) continue

    const srcPort = findOutputPort(srcPorts.outputs, edge.sourceHandle)
    const tgtPort = findInputPort(tgtPorts.inputs, edge.targetHandle)

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
    const ports = portsMap.get(nodeId)
    if (!ports) continue
    const port = findInputPort(ports.inputs, portHandle)
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
    const ports = portsMap.get(node.id)
    if (!ports) continue
    for (const port of ports.inputs) {
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

  // 7. Unknown handle + direction — output→output or input→input
  for (const edge of edges) {
    const srcNode = nodeMap.get(edge.source)
    const tgtNode = nodeMap.get(edge.target)
    if (!srcNode || !tgtNode) continue

    const srcPorts = portsMap.get(edge.source)
    const tgtPorts = portsMap.get(edge.target)
    if (!srcPorts || !tgtPorts) continue

    const srcPort = findOutputPort(srcPorts.outputs, edge.sourceHandle)
    const srcInputPort = findInputPort(srcPorts.inputs, edge.sourceHandle)
    const tgtPort = findInputPort(tgtPorts.inputs, edge.targetHandle)
    const tgtOutputPort = findOutputPort(tgtPorts.outputs, edge.targetHandle)

    // UNKNOWN_HANDLE — a named handle must exist on the node's effective ports
    if (edge.sourceHandle && !srcPort && !srcInputPort) {
      errors.push({
        code: 'UNKNOWN_HANDLE',
        message: `连线 ${edge.id} 的源端口 ${edge.sourceHandle} 不存在于节点 ${srcNode.id} 的端口列表`,
        edgeId: edge.id,
        nodeId: srcNode.id,
        portId: edge.sourceHandle,
      })
    }
    if (edge.targetHandle && !tgtPort && !tgtOutputPort) {
      errors.push({
        code: 'UNKNOWN_HANDLE',
        message: `连线 ${edge.id} 的目标端口 ${edge.targetHandle} 不存在于节点 ${tgtNode.id} 的端口列表`,
        edgeId: edge.id,
        nodeId: tgtNode.id,
        portId: edge.targetHandle,
      })
    }

    // If source handle is an input port or target handle is an output port
    if (!srcPort && srcInputPort) {
      errors.push({
        code: 'DIRECTION',
        message: `连线 ${edge.id} 不能从输入端口 ${edge.sourceHandle ?? ''} 发出`,
        edgeId: edge.id,
      })
    }
    if (!tgtPort && tgtOutputPort) {
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
 * Port type/cardinality checks use each node's effective ports (instance-level
 * `data.ports` first, catalog fallback) so module extension ports are checked.
 * A would-be cycle is rejected here so drag-time conclusions match
 * `validateGraph` and backend start validation.
 *
 * @param source        Source node ID
 * @param sourceHandle  Source port (handle) ID
 * @param target        Target node ID
 * @param targetHandle  Target port (handle) ID
 * @param nodes         Full node records (preferred) or a node ID → NodeKind map
 * @param catalog       Node manifest catalog (defaults to NODE_CATALOG), used
 *                      as fallback when a node has no `data.ports`
 * @param existingEdges Current edges in the graph
 * @returns null if valid, or a single ValidationError
 */
export function validateConnection(
  source: string,
  sourceHandle: string | undefined,
  target: string,
  targetHandle: string | undefined,
  nodes: NodeInput = {},
  catalog: Record<string, NodeManifest> = NODE_CATALOG,
  existingEdges: EdgeRecord[] = [],
): ValidationError | null {
  // Resolve source and target ports via their effective ports
  const nodeMap = toNodeMap(nodes)
  const srcPorts = getNodeEffectivePorts(nodeMap.get(source), catalog)
  const tgtPorts = getNodeEffectivePorts(nodeMap.get(target), catalog)

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

  const srcOutputPort = findOutputPort(srcPorts.outputs, sourceHandle)
  const srcInputPort = findInputPort(srcPorts.inputs, sourceHandle)
  const tgtOutputPort = findOutputPort(tgtPorts.outputs, targetHandle)
  const tgtInputPort = findInputPort(tgtPorts.inputs, targetHandle)

  // Unknown handle — a named handle must exist on the node's effective ports
  if (sourceHandle && !srcOutputPort && !srcInputPort) {
    return {
      code: 'UNKNOWN_HANDLE',
      message: `源端口 ${sourceHandle} 不存在`,
      portId: sourceHandle,
    }
  }
  if (targetHandle && !tgtInputPort && !tgtOutputPort) {
    return {
      code: 'UNKNOWN_HANDLE',
      message: `目标端口 ${targetHandle} 不存在`,
      portId: targetHandle,
    }
  }

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

  // Cycle — the new edge must not close a loop
  if (wouldCreateCycle(source, target, existingEdges)) {
    return {
      code: 'CYCLE',
      message: '连线会形成环路，工作流不能包含循环',
    }
  }

  return null
}
