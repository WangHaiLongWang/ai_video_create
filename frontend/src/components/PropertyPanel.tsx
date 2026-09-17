import { useState } from 'react'
import { ArrowsClockwise, Check, Pencil, Plus, Trash, Sparkle, SquaresFour } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import { useExecutionStore } from '../stores/executionStore'
import { FieldEditorDialog } from './FieldEditorDialog'
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
    addField, updateField, removeField, updateFieldConfig,
  } = useStudioStore()
  const executionStatus = useExecutionStore((s) => s.status)
  const isRunning = executionStatus === 'running'
  const node = workflow.nodes.find((item) => item.id === selectedNodeId)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingField, setEditingField] = useState<FieldDefinition | null>(null)

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
    removeField(selectedNodeId, fieldId)
    setDialogOpen(false)
    setEditingField(null)
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
          {(node.data.fieldSchema ?? []).map((field) => (
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
                  <button onClick={() => handleEditField(field)}><Pencil size={11} /></button>
                  <button onClick={() => handleDeleteField(field.id)}><Trash size={11} /></button>
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
    </aside>
  )
}
