import { useMemo } from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
} from '@xyflow/react'
import { StudioNodeView } from '../StudioNode'
import { useStudioStore } from '../store'
import { AgentComposer } from './AgentComposer'

export function Canvas() {
  const { workflow, onNodesChange, onEdgesChange, onConnect, selectNode } = useStudioStore()
  const nodeTypes = useMemo(() => ({ studio: StudioNodeView }), [])
  return (
    <main className="canvas-shell">
      <ReactFlow
        nodes={workflow.nodes}
        edges={workflow.edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_, node) => selectNode(node.id)}
        onPaneClick={() => selectNode(null)}
        fitView
        minZoom={0.35}
        maxZoom={1.6}
        deleteKeyCode={['Backspace', 'Delete']}
      >
        <Background variant={BackgroundVariant.Dots} color="#343832" gap={22} size={1} />
        <Controls position="bottom-left" showInteractive={false} />
        <MiniMap position="bottom-right" pannable zoomable nodeColor="#42483e" maskColor="rgba(18, 20, 18, .78)" />
      </ReactFlow>
      <AgentComposer />
    </main>
  )
}
