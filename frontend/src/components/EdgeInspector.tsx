import { useMemo, useState } from 'react'
import { ArrowsClockwise, Trash } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import { NODE_CATALOG } from '../schemas/node-manifest'
import type { EdgeMode } from '../types'

const EDGE_MODES: { value: EdgeMode; label: string; desc: string }[] = [
  { value: 'direct', label: 'direct', desc: '直接传递' },
  { value: 'map', label: 'map', desc: '逐项映射' },
  { value: 'aggregate', label: 'aggregate', desc: '聚合收集' },
  { value: 'direct-by-key', label: 'direct-by-key', desc: '按 Key 直传' },
]

function getPortLabel(nodeKind: string | undefined, handleId: string | null | undefined, direction: 'input' | 'output'): string {
  if (!nodeKind || !handleId) return handleId ?? '?'
  const manifest = NODE_CATALOG[nodeKind as keyof typeof NODE_CATALOG]
  if (!manifest) return handleId
  const ports = direction === 'input' ? manifest.ports.inputs : manifest.ports.outputs
  const port = ports.find((p) => p.id === handleId)
  return port?.label ?? port?.id ?? handleId
}

export function EdgeInspector() {
  const { workflow, selectedEdgeId, updateEdgeData, reconnectEdge, deleteSelectedEdge, selectEdge } = useStudioStore()
  const [confirmDelete, setConfirmDelete] = useState(false)

  const edge = useMemo(
    () => workflow.edges.find((e) => e.id === selectedEdgeId) ?? null,
    [workflow.edges, selectedEdgeId],
  )

  if (!edge) return null

  const sourceNode = workflow.nodes.find((n) => n.id === edge.source)
  const targetNode = workflow.nodes.find((n) => n.id === edge.target)

  const sourceNodeLabel = sourceNode?.data.label ?? edge.source
  const targetNodeLabel = targetNode?.data.label ?? edge.target
  const sourceNodeKind = sourceNode?.data.kind
  const targetNodeKind = targetNode?.data.kind

  const sourcePortLabel = getPortLabel(sourceNodeKind, edge.sourceHandle, 'output')
  const targetPortLabel = getPortLabel(targetNodeKind, edge.targetHandle, 'input')

  const mode = (edge.data?.mode as EdgeMode) ?? 'direct'
  const isMapMode = mode === 'map'
  const isAggregateMode = mode === 'aggregate'
  const isKeyMode = mode === 'direct-by-key'

  function handleDelete() {
    deleteSelectedEdge()
    setConfirmDelete(false)
  }

  return (
    <div className="edge-inspector">
      <div className="panel-heading">
        <span>连线配置</span>
        <ArrowsClockwise size={15} />
      </div>

      <div className="edge-inspector-body">
        {/* Connection info */}
        <div className="edge-connection-info">
          <div className="edge-node-label">
            <span className="edge-direction-badge source">SRC</span>
            <span>{sourceNodeLabel}</span>
          </div>
          <div className="edge-port-label">{sourcePortLabel}</div>

          <div className="edge-arrow">→</div>

          <div className="edge-node-label">
            <span className="edge-direction-badge target">TGT</span>
            <span>{targetNodeLabel}</span>
          </div>
          <div className="edge-port-label">{targetPortLabel}</div>
        </div>

        {/* Editable fields */}
        <div className="edge-fields">
          <label>
            <span>label</span>
            <input
              type="text"
              value={(edge.data?.label as string) ?? ''}
              onChange={(e) => updateEdgeData(edge.id, { label: e.target.value })}
              placeholder="可选标签"
            />
          </label>

          <label>
            <span>mode</span>
            <select
              value={mode}
              onChange={(e) => {
                const newMode = e.target.value as EdgeMode
                const patch: Record<string, unknown> = { mode: newMode }
                // Clear irrelevant path fields when switching modes
                if (newMode !== 'map') patch.sourcePath = undefined
                if (newMode !== 'aggregate') patch.targetPath = undefined
                if (newMode !== 'direct-by-key') patch.itemKey = undefined
                updateEdgeData(edge.id, patch as Partial<import('../types').EdgeData>)
              }}
            >
              {EDGE_MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label} — {m.desc}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>order</span>
            <input
              type="number"
              value={edge.data?.order != null ? String(edge.data.order) : ''}
              onChange={(e) => updateEdgeData(edge.id, { order: e.target.value === '' ? undefined : Number(e.target.value) })}
              placeholder="0"
              min={0}
            />
          </label>

          {isMapMode && (
            <label>
              <span>sourcePath</span>
              <input
                type="text"
                value={(edge.data?.sourcePath as string) ?? ''}
                onChange={(e) => updateEdgeData(edge.id, { sourcePath: e.target.value })}
                placeholder="如 $.scenes[*].image"
              />
            </label>
          )}

          {isAggregateMode && (
            <label>
              <span>targetPath</span>
              <input
                type="text"
                value={(edge.data?.targetPath as string) ?? ''}
                onChange={(e) => updateEdgeData(edge.id, { targetPath: e.target.value })}
                placeholder="如 $.results"
              />
            </label>
          )}

          {isKeyMode && (
            <label>
              <span>itemKey</span>
              <input
                type="text"
                value={(edge.data?.itemKey as string) ?? ''}
                onChange={(e) => updateEdgeData(edge.id, { itemKey: e.target.value })}
                placeholder="如 sceneId"
              />
            </label>
          )}
        </div>

        {/* Validation hint for map/aggregate modes */}
        {(isMapMode || isAggregateMode) && (
          <div className="edge-warning">
            {isMapMode && 'map 模式将对 sourcePath 指定的数组逐项执行下游节点。'}
            {isAggregateMode && 'aggregate 模式将收集所有上游输出到 targetPath 指定的路径。'}
          </div>
        )}

        {/* Delete */}
        <div className="edge-delete-section">
          {!confirmDelete ? (
            <button className="edge-delete-btn" onClick={() => setConfirmDelete(true)}>
              <Trash size={13} /> 删除连线
            </button>
          ) : (
            <div className="edge-delete-confirm">
              <span>确定删除此连线？</span>
              <button className="edge-delete-cancel" onClick={() => setConfirmDelete(false)}>取消</button>
              <button className="edge-delete-ok" onClick={handleDelete}>删除</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
