import { Plus } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import { createNode, nodeCatalog } from '../workflow'
import type { NodeKind } from '../types'

export function NodePalette() {
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
