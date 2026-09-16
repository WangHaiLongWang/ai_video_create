import { useCallback, useMemo } from 'react'
import {
  BaseEdge,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  getSmoothStepPath,
  useReactFlow,
  type EdgeProps,
  type ReactFlowInstance,
} from '@xyflow/react'
import { StudioNodeView } from '../StudioNode'
import { useStudioStore } from '../store'
import { createNode } from '../workflow'
import type { NodeKind } from '../types'
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

function CanvasInner() {
  const { workflow, onNodesChange, onEdgesChange, onConnect, selectNode, setWorkflow } = useStudioStore()
  const reactFlowInstance: ReactFlowInstance = useReactFlow()
  const nodeTypes = useMemo(() => ({ studio: StudioNodeView }), [])
  const edgeTypes = useMemo(() => ({ default: LabelEdge }), [])

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
        onNodeClick={(_, node) => selectNode(node.id)}
        onPaneClick={() => selectNode(null)}
        onDragOver={onDragOver}
        onDrop={onDrop}
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
