import { Plus } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import { createNode, nodeCatalog } from '../workflow'
import type { NodeKind } from '../types'

export function NodePalette() {
  const { workflow, setWorkflow } = useStudioStore()

  const addNode = (kind: NodeKind) => {
    // 节点宽度 228px + 间距 60px = 288px
    const NODE_WIDTH = 228
    const GAP = 60
    const x = 110 + workflow.nodes.length * (NODE_WIDTH + GAP)
    const y = 150 + (workflow.nodes.length % 2) * 70
    const node = createNode(kind, x, y)
    setWorkflow({ ...workflow, nodes: [...workflow.nodes, node] })
  }

  const onDragStart = (event: React.DragEvent, kind: NodeKind) => {
    event.dataTransfer.setData('application/reactflow', kind)
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <aside className="palette">
      <div className="panel-heading">
        <span>节点库</span>
        <button aria-label="添加节点"><Plus size={15} /></button>
      </div>
      <p className="panel-hint">点击或拖拽到画布</p>
      <div className="node-list">
        {(Object.keys(nodeCatalog) as NodeKind[]).map((kind) => (
          <button
            key={kind}
            draggable
            onDragStart={(e) => onDragStart(e, kind)}
            onClick={() => addNode(kind)}
          >
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
