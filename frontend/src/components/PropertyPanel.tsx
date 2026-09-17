import { useState } from 'react'
import { ArrowsClockwise, ArrowUp, ArrowDown, Check, Copy, Pencil, Plus, Trash, Sparkle, SquaresFour } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import { useExecutionStore } from '../stores/executionStore'
import { FieldEditorDialog } from './FieldEditorDialog'
import { PortEditor } from './PortEditor'
import type { FieldDefinition, FieldType } from '../types'

/** 根据执行状态生成提示文本 */
function getRunMessage(status: string): string {
  switch (status) {
    case 'idle': return '准备执行'
    case 'running': return '执行中...'
    case 'completed': return '执行完成'
    case 'failed': return '执行失败'
    case 'cancelled': return '执行已取消'
    default: return status
  }
}

function renderFieldValue(
  field: FieldDefinition,
  value: string | number | boolean | undefined,
  onChange: (v: string | number | boolean) => void,
) {
  switch (field.type) {
    case 'boolean':
      return (
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
        />
      )
    case 'number':
      return (
        <input
          type="number"
          value={value != null ? String(value) : ''}
          onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
        />
      )
    case 'textarea':
      return (
        <textarea
          rows={3}
          value={value != null ? String(value) : ''}
          onChange={(e) => onChange(e.target.value)}
        />
      )
    case 'json':
      return (
        <textarea
          rows={4}
          value={value != null ? String(value) : ''}
          onChange={(e) => onChange(e.target.value)}
          style={{ fontFamily: '"Cascadia Code", monospace', fontSize: 11 }}
        />
      )
    case 'prompt':
      return (
        <textarea
          rows={4}
          value={value != null ? String(value) : ''}
          onChange={(e) => onChange(e.target.value)}
          style={{ lineHeight: 1.5 }}
        />
      )
    case 'select':
      return (
        <select
          value={value != null ? String(value) : ''}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">-- select --</option>
          {field.options?.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      )
    case 'multi_select':
      return (
        <input
          type="text"
          value={value != null ? String(value) : ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder="comma-separated"
        />
      )
    case 'text':
    default:
      return (
        <input
          type="text"
          value={value != null ? String(value) : ''}
          onChange={(e) => onChange(e.target.value)}
        />
      )
  }
}

export function PropertyPanel() {
  const {
    workflow, selectedNodeId, updateConfig,
    addField, updateField, removeField,
    deleteField, reorderFields, duplicateField,
    updateFieldConfig,
  } = useStudioStore()
  const executionStatus = useExecutionStore((s) => s.status)
  const isRunning = executionStatus === 'running'
  const node = workflow.nodes.find((item) => item.id === selectedNodeId)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingField, setEditingField] = useState<FieldDefinition | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<{ fieldId: string; fieldLabel: string } | null>(null)

  function handleAddField() {
    setEditingField(null)
    setDialogOpen(true)
  }

  function handleEditField(f: FieldDefinition) {
    setEditingField(f)
    setDialogOpen(true)
  }

  function handleDeleteField(fieldId: string) {
    if (!selectedNodeId) return
    deleteField(selectedNodeId, fieldId)
    setDialogOpen(false)
    setEditingField(null)
    setDeleteConfirm(null)
  }

  function handleConfirmDelete(fieldId: string, fieldLabel: string) {
    setDeleteConfirm({ fieldId, fieldLabel })
  }

  function handleReorderField(fromIndex: number, toIndex: number) {
    if (!selectedNodeId) return
    const schema = node?.data.fieldSchema ?? []
    if (toIndex < 0 || toIndex >= schema.length) return
    reorderFields(selectedNodeId, fromIndex, toIndex)
  }

  function handleDuplicateField(fieldId: string) {
    if (!selectedNodeId) return
    duplicateField(selectedNodeId, fieldId)
  }

  function handleSaveField(field: FieldDefinition) {
    if (!selectedNodeId) return
    if (editingField) {
      updateField(selectedNodeId, editingField.id, field)
    } else {
      addField(selectedNodeId, field)
    }
    setDialogOpen(false)
    setEditingField(null)
  }

  // Partition config keys into schema-owned and legacy
  const schemaFieldIds = new Set((node?.data.fieldSchema ?? []).map((f) => f.id))
  const legacyConfigKeys = node
    ? Object.keys(node.data.config).filter((k) => !schemaFieldIds.has(k))
    : []

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
          {/* 基础配置 */}
          <div className="selected-title">
            <span>{node.data.label}</span>
            <small>{node.data.kind}</small>
          </div>
          <label>
            <span>label</span>
            <input type="text" value={node.data.label} readOnly />
          </label>
          <label>
            <span>description</span>
            <input type="text" value={node.data.description} readOnly />
          </label>

          {/* 自定义字段 */}
          <div className="prop-section-title">
            <span>自定义字段</span>
            <button onClick={handleAddField}><Plus size={12} /> 添加字段</button>
          </div>
          {(node.data.fieldSchema ?? []).map((field, idx, arr) => (
            <div key={field.id}>
              <div className="prop-field-row">
                <label>
                  <span>
                    {field.label}
                    {field.required && <span style={{ color: '#d47868' }}> *</span>}
                  </span>
                  {renderFieldValue(
                    field,
                    node.data.config[field.id] ?? field.default,
                    (v) => updateFieldConfig(field.id, v),
                  )}
                </label>
                <div className="prop-field-actions">
                  <button
                    onClick={() => handleReorderField(idx, idx - 1)}
                    disabled={idx === 0}
                    title="上移"
                  >
                    <ArrowUp size={11} />
                  </button>
                  <button
                    onClick={() => handleReorderField(idx, idx + 1)}
                    disabled={idx === arr.length - 1}
                    title="下移"
                  >
                    <ArrowDown size={11} />
                  </button>
                  <button onClick={() => handleEditField(field)} title="编辑">
                    <Pencil size={11} />
                  </button>
                  <button onClick={() => handleDuplicateField(field.id)} title="复制">
                    <Copy size={11} />
                  </button>
                  <button onClick={() => handleConfirmDelete(field.id, field.label)} title="删除">
                    <Trash size={11} />
                  </button>
                </div>
              </div>
            </div>
          ))}
          {(node.data.fieldSchema ?? []).length === 0 && legacyConfigKeys.length === 0 && (
            <div style={{ fontSize: 11, color: '#5a6055', marginBottom: 8 }}>
              No custom fields defined
            </div>
          )}

          {/* Provider 配置 (legacy / manifest-owned) */}
          {legacyConfigKeys.length > 0 && (
            <>
              <div className="prop-section-title">
                <span>Provider 配置</span>
              </div>
              {legacyConfigKeys.map((key) => {
                const value = node.data.config[key]
                return (
                  <label key={key}>
                    <span>{key}</span>
                    {typeof value === 'boolean' ? (
                      <input
                        type="checkbox"
                        checked={value}
                        onChange={(event) => updateConfig(key, event.target.checked)}
                      />
                    ) : (
                      <input
                        type={typeof value === 'number' ? 'number' : 'text'}
                        value={String(value)}
                        onChange={(event) => updateConfig(key, typeof value === 'number' ? Number(event.target.value) : event.target.value)}
                      />
                    )}
                  </label>
                )
              })}
            </>
          )}

          {/* 端口 */}
          <div className="prop-section-title">
            <span>端口</span>
          </div>
          <PortEditor
            inputs={node.data.ports?.inputs ?? []}
            outputs={node.data.ports?.outputs ?? []}
          />
        </div>
      )}
      <div className={`run-summary ${isRunning ? 'is-active' : ''}`}>
        {isRunning ? <Sparkle size={18} weight="fill" /> : <Check size={18} weight="bold" />}
        <div><strong>{isRunning ? 'Mock 执行中' : '运行状态'}</strong><span>{getRunMessage(executionStatus)}</span></div>
      </div>

      {dialogOpen && (
        <FieldEditorDialog
          field={editingField}
          onSave={handleSaveField}
          onDelete={editingField ? () => handleDeleteField(editingField.id) : undefined}
          onClose={() => { setDialogOpen(false); setEditingField(null) }}
        />
      )}

      {deleteConfirm && (
        <div className="field-dialog-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="field-dialog" onClick={(e) => e.stopPropagation()} style={{ width: 'min(400px, calc(100% - 40px))' }}>
            <h3>确认删除</h3>
            <p style={{ fontSize: 12, color: '#c5c9be', lineHeight: 1.6, margin: '0 0 6px' }}>
              确定要删除字段 '{deleteConfirm.fieldLabel}' 吗？
            </p>
            <p style={{ fontSize: 11, color: '#8b9286', lineHeight: 1.5, margin: '0 0 4px' }}>
              对应的配置值也将被删除。
            </p>
            <p style={{ fontSize: 11, color: '#737a6e', lineHeight: 1.5, margin: '0 0 16px' }}>
              此操作可以撤销 (Ctrl+Z)。
            </p>
            <div className="field-dialog-actions">
              <button className="field-dialog-cancel" onClick={() => setDeleteConfirm(null)}>取消</button>
              <button className="field-dialog-delete" onClick={() => handleDeleteField(deleteConfirm.fieldId)}>删除</button>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}
