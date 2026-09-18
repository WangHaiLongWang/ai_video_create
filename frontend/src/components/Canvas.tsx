import { useCallback, useMemo } from 'react'
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
  type ReactFlowInstance,
} from '@xyflow/react'
import type { ConnectionLineComponentProps } from '@xyflow/react/dist/esm/types/edges'
import { StudioNodeView } from '../StudioNode'
import { useStudioStore } from '../store'
import { createNode } from '../workflow'
import { validateConnection as validateConnectionNew } from '../schemas/graph-validation'
import { NODE_CATALOG } from '../schemas/node-manifest'
import type { NodeKind, EnhancedEdge } from '../types'
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

function CanvasInner() {
  const { workflow, onNodesChange, onEdgesChange, onConnect, selectNode, setWorkflow, setConnectingFrom } = useStudioStore()
  const reactFlowInstance: ReactFlowInstance = useReactFlow()
  const nodeTypes = useMemo(() => ({ studio: StudioNodeView }), [])
  const edgeTypes = useMemo(() => ({ default: LabelEdge }), [])

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
        onNodeClick={(_, node) => selectNode(node.id)}
        onPaneClick={() => selectNode(null)}
        onDragOver={onDragOver}
        onDrop={onDrop}
        isValidConnection={isValidConnection}
        connectionLineComponent={CustomConnectionLine}
        connectionMode={ConnectionMode.Strict}
        connectionLineStyle={{ stroke: '#d6f06d', strokeWidth: 2 }}
        connectionRadius={20}
        fitView
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
