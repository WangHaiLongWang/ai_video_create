import { useMemo, useState } from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  ArrowsClockwise,
  CaretDown,
  Check,
  FloppyDisk,
  GearSix,
  Pause,
  Play,
  Plus,
  Robot,
  Sparkle,
  SquaresFour,
} from '@phosphor-icons/react'
import { StudioNodeView } from './StudioNode'
import { useStudioStore } from './store'
import { createNode, createPromptToVideoWorkflow, nodeCatalog } from './workflow'
import type { NodeKind, StudioNode } from './types'

function TopBar() {
  const { workflow, isRunning, runMock, stopRun } = useStudioStore()
  return (
    <header className="topbar">
      <div className="brand-mark"><SquaresFour size={19} weight="fill" /></div>
      <div className="title-group">
        <strong>ai_video_create</strong>
        <span>/</span>
        <button>{workflow.name}<CaretDown size={12} /></button>
      </div>
      <div className="top-actions">
        <button className="icon-button" aria-label="设置"><GearSix size={18} /></button>
        <button className="secondary-button"><FloppyDisk size={17} />已自动保存</button>
        {isRunning ? (
          <button className="stop-button" onClick={stopRun}><Pause size={17} weight="fill" />停止</button>
        ) : (
          <button className="run-button" onClick={runMock}><Play size={17} weight="fill" />运行工作流</button>
        )}
      </div>
    </header>
  )
}

function NodePalette() {
  const { workflow, setWorkflow } = useStudioStore()
  const addNode = (kind: NodeKind) => {
    const node = createNode(kind, 160 + workflow.nodes.length * 28, 380)
    setWorkflow({ ...workflow, nodes: [...workflow.nodes, node] })
  }
  return (
    <aside className="palette">
      <div className="panel-heading">
        <span>节点库</span>
        <button aria-label="添加节点"><Plus size={15} /></button>
      </div>
      <p className="panel-hint">点击添加到画布</p>
      <div className="node-list">
        {(Object.keys(nodeCatalog) as NodeKind[]).map((kind) => (
          <button key={kind} onClick={() => addNode(kind)}>
            <span>{nodeCatalog[kind].label}</span>
            <small>{nodeCatalog[kind].outputType ?? '终点'}</small>
          </button>
        ))}
      </div>
      <div className="palette-footer">
        <span>本地服务</span>
        <strong><i />已连接</strong>
      </div>
    </aside>
  )
}

function PropertyPanel() {
  const { workflow, selectedNodeId, updateConfig, runMessage, isRunning } = useStudioStore()
  const node = workflow.nodes.find((item) => item.id === selectedNodeId)
  return (
    <aside className="properties">
      <div className="panel-heading"><span>节点配置</span><ArrowsClockwise size={15} /></div>
      {!node ? (
        <div className="empty-panel">
          <SquaresFour size={30} weight="duotone" />
          <strong>选择一个节点</strong>
          <p>在画布中选择节点后，可以在这里调整生成参数。</p>
        </div>
      ) : (
        <div className="property-form">
          <div className="selected-title">
            <span>{node.data.label}</span>
            <small>{node.data.kind}</small>
          </div>
          {Object.entries(node.data.config).map(([key, value]) => (
            <label key={key}>
              <span>{key}</span>
              {typeof value === 'boolean' ? (
                <input type="checkbox" checked={value} onChange={(event) => updateConfig(key, event.target.checked)} />
              ) : (
                <input
                  type={typeof value === 'number' ? 'number' : 'text'}
                  value={String(value)}
                  onChange={(event) => updateConfig(key, typeof value === 'number' ? Number(event.target.value) : event.target.value)}
                />
              )}
            </label>
          ))}
        </div>
      )}
      <div className={`run-summary ${isRunning ? 'is-active' : ''}`}>
        {isRunning ? <Sparkle size={18} weight="fill" /> : <Check size={18} weight="bold" />}
        <div><strong>{isRunning ? 'Mock 执行中' : '运行状态'}</strong><span>{runMessage}</span></div>
      </div>
    </aside>
  )
}

function AgentComposer() {
  const [prompt, setPrompt] = useState('创建一个 5 镜头的未来城市短视频流程')
  const [open, setOpen] = useState(true)
  const setWorkflow = useStudioStore((state) => state.setWorkflow)

  const generate = () => {
    const count = Number(prompt.match(/(\d+)\s*镜头/)?.[1] ?? 5)
    const workflow = createPromptToVideoWorkflow(prompt)
    const storyboard = workflow.nodes.find((node) => node.data.kind === 'storyboard')
    if (storyboard) storyboard.data.config.scenes = Math.min(Math.max(count, 1), 20)
    setWorkflow(workflow)
  }

  if (!open) return <button className="agent-fab" onClick={() => setOpen(true)} aria-label="打开 Agent"><Robot size={21} /></button>
  return (
    <section className="agent-composer">
      <div className="agent-title"><Robot size={18} weight="duotone" /><strong>Workflow Agent</strong><button onClick={() => setOpen(false)}>收起</button></div>
      <div className="agent-input">
        <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} aria-label="描述想要创建的工作流" />
        <button onClick={generate}><Sparkle size={17} weight="fill" />生成流程</button>
      </div>
      <p>本地规则模式。接入 LLM 后将生成结构化 WorkflowSpec，并在应用前展示差异。</p>
    </section>
  )
}

function Canvas() {
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

export default function App() {
  return (
    <ReactFlowProvider>
      <div className="app-shell">
        <TopBar />
        <NodePalette />
        <Canvas />
        <PropertyPanel />
      </div>
    </ReactFlowProvider>
  )
}
