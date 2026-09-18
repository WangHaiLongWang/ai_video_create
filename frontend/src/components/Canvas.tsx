import { useCallback, useMemo, useRef, useState } from 'react'
import {
  BaseEdge,
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  MiniMap,
  ReactFlow,
  getBezierPath,
  getSmoothStepPath,
  useReactFlow,
  type Connection,
  type EdgeProps,
  type IsValidConnection,
  type OnConnectStart,
  type OnConnectEnd,
  type OnReconnect,
  type ReactFlowInstance,
  type Viewport,
} from '@xyflow/react'
import type { ConnectionLineComponentProps } from '@xyflow/react/dist/esm/types/edges'
import { StudioNodeView } from '../StudioNode'
import { useStudioStore } from '../store'
import { createNode } from '../workflow'
import { validateConnection as validateConnectionNew } from '../schemas/graph-validation'
import { NODE_CATALOG } from '../schemas/node-manifest'
import type { NodeKind, EnhancedEdge, StudioNode } from '../types'
import { AgentComposer } from './AgentComposer'

function LabelEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, style, markerEnd }: EdgeProps) {
  const [edgePath, labelX, labelY] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition })

  return (
    <>
      <BaseEdge id={id} path={edgePath} style={style} markerEnd={markerEnd} />
      {data?.label && (
        <foreignObject x={labelX - 30} y={labelY - 12} width={60} height={24} className="edge-label-container">
          <span className="edge-label">{data.label as string}</span>
        </foreignObject>
      )}
    </>
  )
}

/**
 * Custom connection line that shows green for valid and red for invalid
 * connections while the user is dragging between ports.
 */
function CustomConnectionLine({
  fromX, fromY, toX, toY,
  fromPosition, toPosition,
  connectionStatus,
}: ConnectionLineComponentProps) {
  const [edgePath] = getBezierPath({
    sourceX: fromX,
    sourceY: fromY,
    sourcePosition: fromPosition,
    targetX: toX,
    targetY: toY,
    targetPosition: toPosition,
  })

  const isValid = connectionStatus !== 'invalid'

  return (
    <path
      d={edgePath}
      fill="none"
      stroke={isValid ? '#d6f06d' : '#d9534f'}
      strokeWidth={2}
      strokeDasharray={isValid ? undefined : '6 3'}
      className="connection-line-custom"
    />
  )
}

// ==================== Auto-Layout ====================

const LAYER_GAP_X = 320
const NODE_GAP_Y = 100
const NODE_WIDTH = 228
const NODE_HEIGHT = 80

/**
 * Compute a topological-sort-based layered layout for the given nodes and edges.
 * Nodes with no incoming edges start at layer 0; each subsequent layer is one step deeper.
 * Within each layer, nodes are spread vertically with even spacing.
 * Returns a Map<nodeId, {x, y}>.
 */
function computeAutoLayout(nodes: StudioNode[], edges: EnhancedEdge[]): Map<string, { x: number; y: number }> {
  const result = new Map<string, { x: number; y: number }>()

  if (nodes.length === 0) return result

  // Build adjacency and in-degree
  const adjacency = new Map<string, string[]>()
  const inDegree = new Map<string, number>()
  for (const n of nodes) {
    adjacency.set(n.id, [])
    inDegree.set(n.id, 0)
  }
  for (const e of edges) {
    if (adjacency.has(e.source) && inDegree.has(e.target)) {
      adjacency.get(e.source)!.push(e.target)
      inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1)
    }
  }

  // Kahn's algorithm to determine layers
  const layers = new Map<string, number>()
  const queue: string[] = []
  for (const [id, deg] of inDegree) {
    if (deg === 0) {
      queue.push(id)
      layers.set(id, 0)
    }
  }

  while (queue.length > 0) {
    const current = queue.shift()!
    const currentLayer = layers.get(current)!
    for (const neighbor of adjacency.get(current) ?? []) {
      const newDegree = (inDegree.get(neighbor) ?? 1) - 1
      inDegree.set(neighbor, newDegree)
      const neighborLayer = layers.get(neighbor) ?? 0
      layers.set(neighbor, Math.max(neighborLayer, currentLayer + 1))
      if (newDegree === 0) {
        queue.push(neighbor)
      }
    }
  }

  // Assign layers for any disconnected nodes (no edges at all)
  for (const n of nodes) {
    if (!layers.has(n.id)) {
      layers.set(n.id, 0)
    }
  }

  // Group nodes by layer
  const layerGroups = new Map<number, string[]>()
  for (const [id, layer] of layers) {
    const group = layerGroups.get(layer) ?? []
    group.push(id)
    layerGroups.set(layer, group)
  }

  // Position nodes
  const sortedLayers = Array.from(layerGroups.keys()).sort((a, b) => a - b)
  for (const layerIdx of sortedLayers) {
    const group = layerGroups.get(layerIdx)!
    const totalHeight = group.length * NODE_HEIGHT + (group.length - 1) * NODE_GAP_Y
    const startY = -totalHeight / 2
    for (let i = 0; i < group.length; i++) {
      result.set(group[i], {
        x: layerIdx * LAYER_GAP_X,
        y: startY + i * (NODE_HEIGHT + NODE_GAP_Y),
      })
    }
  }

  return result
}

// ==================== CanvasToolbar ====================

function CanvasToolbar({ reactFlowInstance }: { reactFlowInstance: ReactFlowInstance }) {
  const workflow = useStudioStore((s) => s.workflow)
  const applyAutoLayout = useStudioStore((s) => s.applyAutoLayout)
  const selectedNodeIds = useStudioStore((s) => s.selectedNodeIds)

  const handleFitView = useCallback(() => {
    reactFlowInstance.fitView({ padding: 0.2, duration: 400 })
  }, [reactFlowInstance])

  const handleCenter = useCallback(() => {
    reactFlowInstance.setCenter(0, 0, { duration: 400 })
  }, [reactFlowInstance])

  const handleAutoLayout = useCallback(() => {
    const positions = computeAutoLayout(workflow.nodes, workflow.edges)
    applyAutoLayout(positions)
    // After applying, fit view to show the new layout
    setTimeout(() => {
      reactFlowInstance.fitView({ padding: 0.15, duration: 500 })
    }, 50)
  }, [workflow.nodes, workflow.edges, applyAutoLayout, reactFlowInstance])

  return (
    <div className="canvas-toolbar">
      <button
        className="canvas-toolbar-btn"
        onClick={handleFitView}
        title="适应画布 (Fit View)"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M2 5V3a1 1 0 011-1h2M11 2h2a1 1 0 011 1v2M14 11v2a1 1 0 01-1 1h-2M5 14H3a1 1 0 01-1-1v-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span>适应</span>
      </button>
      <button
        className="canvas-toolbar-btn"
        onClick={handleCenter}
        title="居中 (Center)"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.5"/>
          <path d="M8 2v3M8 11v3M2 8h3M11 8h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
        <span>居中</span>
      </button>
      <button
        className="canvas-toolbar-btn"
        onClick={handleAutoLayout}
        title="自动布局 (Auto Layout)"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <rect x="1" y="3" width="4" height="4" rx="1" stroke="currentColor" strokeWidth="1.2"/>
          <rect x="6" y="1" width="4" height="4" rx="1" stroke="currentColor" strokeWidth="1.2"/>
          <rect x="6" y="11" width="4" height="4" rx="1" stroke="currentColor" strokeWidth="1.2"/>
          <rect x="11" y="3" width="4" height="4" rx="1" stroke="currentColor" strokeWidth="1.2"/>
        </svg>
        <span>布局</span>
      </button>
      {selectedNodeIds.length > 1 && (
        <div className="canvas-selection-badge">
          {selectedNodeIds.length} 个节点已选
        </div>
      )}
    </div>
  )
}

// ==================== CanvasInner ====================

function CanvasInner() {
  const { workflow, onNodesChange, onEdgesChange, onConnect, selectNode, selectEdge, reconnectEdge, setWorkflow, setConnectingFrom, saveViewport, beginBatchHistory, endBatchHistory, toggleNodeSelection, selectedNodeIds, clearSelection } = useStudioStore()
  const reactFlowInstance: ReactFlowInstance = useReactFlow()
  const nodeTypes = useMemo(() => ({ studio: StudioNodeView }), [])
  const edgeTypes = useMemo(() => ({ default: LabelEdge }), [])

  // Viewport persistence: debounce viewport save
  const viewportTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onMoveEnd = useCallback((_: unknown, viewport: Viewport) => {
    if (viewportTimerRef.current) clearTimeout(viewportTimerRef.current)
    viewportTimerRef.current = setTimeout(() => {
      saveViewport({ x: viewport.x, y: viewport.y, zoom: viewport.zoom })
    }, 500)
  }, [saveViewport])

  // Build the initial viewport from the workflow spec (used by ReactFlow as defaultViewport)
  const defaultViewport = useMemo(() => {
    const v = workflow.viewport
    return v ? { x: v.x, y: v.y, zoom: v.zoom } : { x: 0, y: 0, zoom: 1 }
  }, [workflow.viewport])

  const isValidConnection: IsValidConnection<EnhancedEdge> = useCallback((connection) => {
    const nodeKinds: Record<string, NodeKind> = {}
    workflow.nodes.forEach(n => { nodeKinds[n.id] = n.data.kind })
    const error = validateConnectionNew(
      connection.source, connection.sourceHandle ?? undefined,
      connection.target, connection.targetHandle ?? undefined,
      nodeKinds, NODE_CATALOG, workflow.edges,
    )
    return !error
  }, [workflow.nodes, workflow.edges])

  // --- Connection session tracking ---
  const onConnectStart: OnConnectStart = useCallback((_, { nodeId, handleId, handleType }) => {
    if (handleType !== 'source' || !nodeId || !handleId) return

    const node = workflow.nodes.find(n => n.id === nodeId)
    if (!node) return

    const manifest = NODE_CATALOG[node.data.kind]
    if (!manifest) return

    const outputPort = manifest.ports.outputs.find(p => p.id === handleId)
    if (!outputPort) return

    setConnectingFrom({ nodeId, handleId, portType: outputPort.type })
  }, [workflow.nodes, setConnectingFrom])

  const onConnectEnd: OnConnectEnd = useCallback(() => {
    setConnectingFrom(null)
  }, [setConnectingFrom])

  // --- Edge selection ---
  const onEdgeClick = useCallback((_: React.MouseEvent, edge: EnhancedEdge) => {
    selectEdge(edge.id)
  }, [selectEdge])

  // --- Edge reconnection ---
  const onReconnect: OnReconnect<EnhancedEdge> = useCallback((oldEdge, newConnection) => {
    reconnectEdge(
      oldEdge.id,
      newConnection.source,
      newConnection.target,
      newConnection.sourceHandle ?? '',
      newConnection.targetHandle ?? '',
    )
  }, [reconnectEdge])

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    const kind = event.dataTransfer.getData('application/reactflow') as NodeKind
    if (!kind) return

    const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect()
    const position = reactFlowInstance.screenToFlowPosition({
      x: event.clientX - bounds.left,
      y: event.clientY - bounds.top,
    })
    const node = createNode(kind, position.x, position.y)
    setWorkflow({ ...workflow, nodes: [...workflow.nodes, node] })
  }, [workflow, setWorkflow, reactFlowInstance])

  // --- Semantic undo: batch node drag into one history step ---
  const onNodeDragStart = useCallback((_: React.MouseEvent, node: StudioNode) => {
    // Capture workflow snapshot BEFORE any drag position changes arrive.
    beginBatchHistory(useStudioStore.getState().workflow)
  }, [beginBatchHistory])

  const onNodeDragStop = useCallback(() => {
    endBatchHistory()
  }, [endBatchHistory])

  return (
    <>
      <ReactFlow
        nodes={workflow.nodes}
        edges={workflow.edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onConnectStart={onConnectStart}
        onConnectEnd={onConnectEnd}
        onNodeClick={(event, node) => {
          if (event.shiftKey || event.metaKey || event.ctrlKey) {
            toggleNodeSelection(node.id)
          } else {
            selectNode(node.id)
          }
        }}
        onNodeDragStart={onNodeDragStart}
        onNodeDragStop={onNodeDragStop}
        onEdgeClick={onEdgeClick}
        onReconnect={onReconnect}
        onPaneClick={() => clearSelection()}
        onMoveEnd={onMoveEnd}
        onDragOver={onDragOver}
        onDrop={onDrop}
        isValidConnection={isValidConnection}
        connectionLineComponent={CustomConnectionLine}
        connectionMode={ConnectionMode.Strict}
        connectionLineStyle={{ stroke: '#d6f06d', strokeWidth: 2 }}
        connectionRadius={20}
        defaultViewport={defaultViewport}
        minZoom={0.35}
        maxZoom={1.6}
        deleteKeyCode={['Backspace', 'Delete']}
        panOnDrag
        nodesDraggable
        nodesConnectable
        selectNodesOnDrag={false}
      >
        <Background variant={BackgroundVariant.Dots} color="#343832" gap={22} size={1} />
        <Controls position="bottom-left" showInteractive={false} />
        <MiniMap position="bottom-right" pannable zoomable nodeColor="#42483e" maskColor="rgba(18, 20, 18, .78)" />
        <CanvasToolbar reactFlowInstance={reactFlowInstance} />
      </ReactFlow>
    </>
  )
}

export function Canvas() {
  return (
    <main className="canvas-shell">
      <CanvasInner />
      <AgentComposer />
    </main>
  )
}
