import { useState, useMemo } from 'react'
import { ArrowDown, ArrowUp, Plus, Pencil, Trash, Warning, Lock, LinkBreak } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import { NODE_CATALOG } from '../schemas/node-manifest'
import { PortEditorDialog } from './PortEditorDialog'
import type { PortInfo } from '../types'

interface PortEditorProps {
  nodeId: string
  inputs: PortInfo[]
  outputs: PortInfo[]
}

/** Get the set of port IDs defined in the node's manifest (core ports that cannot be deleted) */
function getManifestPortIds(kind: string): Set<string> {
  const manifest = NODE_CATALOG[kind as keyof typeof NODE_CATALOG]
  if (!manifest) return new Set()
  const ids = new Set<string>()
  for (const p of manifest.ports.inputs) ids.add(p.id)
  for (const p of manifest.ports.outputs) ids.add(p.id)
  return ids
}

function EmptyPorts({ label }: { label: string }) {
  return (
    <div className="port-empty">
      <span>{label}</span>
    </div>
  )
}

export function PortEditor({ nodeId, inputs, outputs }: PortEditorProps) {
  const { workflow, addPort, updatePort, deletePort } = useStudioStore()
  const node = workflow.nodes.find((n) => n.id === nodeId)
  const kind = node?.data.kind ?? ''

  const manifestPortIds = useMemo(() => getManifestPortIds(kind), [kind])

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogDirection, setDialogDirection] = useState<'input' | 'output'>('input')
  const [editingPort, setEditingPort] = useState<PortInfo | null>(null)

  // Delete confirmation state
  const [deleteConfirm, setDeleteConfirm] = useState<{
    direction: 'input' | 'output'
    portId: string
    portLabel: string
    affectedEdgeCount: number
  } | null>(null)

  function handleAddPort(direction: 'input' | 'output') {
    setDialogDirection(direction)
    setEditingPort(null)
    setDialogOpen(true)
  }

  function handleEditPort(direction: 'input' | 'output', port: PortInfo) {
    setDialogDirection(direction)
    setEditingPort(port)
    setDialogOpen(true)
  }

  function handleRequestDelete(direction: 'input' | 'output', port: PortInfo) {
    const affectedEdgeCount = workflow.edges.filter(
      (e) =>
        (e.source === nodeId && e.sourceHandle === port.id) ||
        (e.target === nodeId && e.targetHandle === port.id),
    ).length
    setDeleteConfirm({
      direction,
      portId: port.id,
      portLabel: port.label || port.id,
      affectedEdgeCount,
    })
  }

  function handleConfirmDelete() {
    if (!deleteConfirm) return
    deletePort(nodeId, deleteConfirm.direction, deleteConfirm.portId)
    setDeleteConfirm(null)
  }

  function handleSavePort(port: PortInfo) {
    if (editingPort) {
      updatePort(nodeId, dialogDirection, editingPort.id, port)
    } else {
      addPort(nodeId, dialogDirection, port)
    }
    setDialogOpen(false)
    setEditingPort(null)
  }

  // Build existing port IDs for uniqueness validation
  const existingPortIds = useMemo(() => {
    const ids = new Set<string>()
    for (const p of inputs) ids.add(p.id)
    for (const p of outputs) ids.add(p.id)
    return Array.from(ids)
  }, [inputs, outputs])

  return (
    <div className="port-editor">
      {/* Input ports section */}
      <div className="port-section">
        <div className="port-section-header">
          <span>输入端口 ({inputs.length})</span>
          <button className="port-section-add-btn" onClick={() => handleAddPort('input')} title="添加输入端口">
            <Plus size={11} />
          </button>
        </div>
        {inputs.length === 0 ? (
          <EmptyPorts label="无输入端口" />
        ) : (
          inputs.map((port) => {
            const isCore = manifestPortIds.has(port.id)
            return (
              <div key={port.id} className="port-row">
                <ArrowDown size={13} color="#6ee7b7" weight="bold" />
                <span className="port-row-label" title={port.id}>{port.label || port.id}</span>
                <span className={`port-type-badge port-type-badge--${port.type}`}>
                  {port.type}
                </span>
                {port.required && (
                  <span title="必填"><Warning size={11} color="#fbbf24" weight="fill" /></span>
                )}
                <span className="port-cardinality">
                  {port.cardinality === 'many' ? '0..*' : '1'}
                </span>
                <div className="port-row-actions">
                  {isCore ? (
                    <span title="核心端口，不可删除" className="port-lock-icon">
                      <Lock size={11} color="#5a6055" weight="fill" />
                    </span>
                  ) : (
                    <>
                      <button
                        className="port-action-btn"
                        onClick={() => handleEditPort('input', port)}
                        title="编辑端口"
                      >
                        <Pencil size={11} />
                      </button>
                      <button
                        className="port-action-btn port-action-btn--danger"
                        onClick={() => handleRequestDelete('input', port)}
                        title="删除端口"
                      >
                        <Trash size={11} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Output ports section */}
      <div className="port-section">
        <div className="port-section-header">
          <span>输出端口 ({outputs.length})</span>
          <button className="port-section-add-btn" onClick={() => handleAddPort('output')} title="添加输出端口">
            <Plus size={11} />
          </button>
        </div>
        {outputs.length === 0 ? (
          <EmptyPorts label="无输出端口" />
        ) : (
          outputs.map((port) => {
            const isCore = manifestPortIds.has(port.id)
            return (
              <div key={port.id} className="port-row">
                <ArrowUp size={13} color="#93c5fd" weight="bold" />
                <span className="port-row-label" title={port.id}>{port.label || port.id}</span>
                <span className={`port-type-badge port-type-badge--${port.type}`}>
                  {port.type}
                </span>
                {port.required && (
                  <span title="必填"><Warning size={11} color="#fbbf24" weight="fill" /></span>
                )}
                <span className="port-cardinality">
                  {port.cardinality === 'many' ? '0..*' : '1'}
                </span>
                <div className="port-row-actions">
                  {isCore ? (
                    <span title="核心端口，不可删除" className="port-lock-icon">
                      <Lock size={11} color="#5a6055" weight="fill" />
                    </span>
                  ) : (
                    <>
                      <button
                        className="port-action-btn"
                        onClick={() => handleEditPort('output', port)}
                        title="编辑端口"
                      >
                        <Pencil size={11} />
                      </button>
                      <button
                        className="port-action-btn port-action-btn--danger"
                        onClick={() => handleRequestDelete('output', port)}
                        title="删除端口"
                      >
                        <Trash size={11} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Port Editor Dialog */}
      {dialogOpen && (
        <PortEditorDialog
          direction={dialogDirection}
          port={editingPort}
          existingPortIds={existingPortIds}
          onSave={handleSavePort}
          onDelete={editingPort ? () => {
            handleRequestDelete(dialogDirection, editingPort)
            setDialogOpen(false)
            setEditingPort(null)
          } : undefined}
          onClose={() => { setDialogOpen(false); setEditingPort(null) }}
        />
      )}

      {/* Delete Confirmation Dialog */}
      {deleteConfirm && (
        <div className="field-dialog-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="field-dialog" onClick={(e) => e.stopPropagation()} style={{ width: 'min(400px, calc(100% - 40px))' }}>
            <h3>确认删除端口</h3>
            <p style={{ fontSize: 12, color: '#c5c9be', lineHeight: 1.6, margin: '0 0 6px' }}>
              确定要删除端口 '{deleteConfirm.portLabel}' 吗？
            </p>
            {deleteConfirm.affectedEdgeCount > 0 && (
              <p style={{ fontSize: 11, color: '#d47868', lineHeight: 1.5, margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: 4 }}>
                <LinkBreak size={12} weight="bold" />
                此操作将同时删除 {deleteConfirm.affectedEdgeCount} 条关联的连线。
              </p>
            )}
            <p style={{ fontSize: 11, color: '#737a6e', lineHeight: 1.5, margin: '0 0 16px' }}>
              此操作可以撤销 (Ctrl+Z)。
            </p>
            <div className="field-dialog-actions">
              <button className="field-dialog-cancel" onClick={() => setDeleteConfirm(null)}>取消</button>
              <button className="field-dialog-delete" onClick={handleConfirmDelete}>删除</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
