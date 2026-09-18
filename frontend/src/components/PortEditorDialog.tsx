import { useState } from 'react'
import { Plus, Trash } from '@phosphor-icons/react'
import type { PortInfo } from '../types'
import type { Cardinality, PortType } from '../schemas/node-manifest'

// Allowed port types
const PORT_TYPES: PortType[] = ['text', 'scene', 'image', 'video', 'audio', 'asset', 'any']
const PORT_TYPE_LABELS: Record<PortType, string> = {
  text: 'text',
  scene: 'scene',
  image: 'image',
  video: 'video',
  audio: 'audio',
  asset: 'asset',
  any: 'any',
}
const CARDINALITY_LABELS: Record<Cardinality, string> = {
  one: '1 (单个)',
  many: '0..* (多个)',
}

// snake_case validation
const SNAKE_CASE_RE = /^[a-z][a-z0-9]*(_[a-z0-9]+)*$/

function toSnakeCase(s: string): string {
  return s
    .replace(/([A-Z])/g, '_$1')
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, '')
    .replace(/^_/, '')
    .replace(/_+/g, '_')
}

export interface PortEditorDialogProps {
  direction: 'input' | 'output'
  port?: PortInfo | null  // null = add new
  existingPortIds: string[]
  onSave: (port: PortInfo) => void
  onDelete?: () => void
  onClose: () => void
}

export function PortEditorDialog({
  direction,
  port,
  existingPortIds,
  onSave,
  onDelete,
  onClose,
}: PortEditorDialogProps) {
  const isEditing = port != null

  const [id, setId] = useState(port?.id ?? '')
  const [label, setLabel] = useState(port?.label ?? '')
  const [type, setType] = useState<PortType>((port?.type as PortType) ?? 'text')
  const [required, setRequired] = useState(port?.required ?? false)
  const [cardinality, setCardinality] = useState<Cardinality>(port?.cardinality ?? 'one')
  const [idError, setIdError] = useState('')

  function handleLabelChange(v: string) {
    setLabel(v)
    if (!isEditing) {
      const snake = toSnakeCase(v)
      setId(snake)
      if (!SNAKE_CASE_RE.test(snake)) {
        setIdError('ID must be snake_case')
      } else if (existingPortIds.includes(snake)) {
        setIdError('Port ID must be unique within the node')
      } else {
        setIdError('')
      }
    }
  }

  function handleIdChange(v: string) {
    setId(v)
    if (!SNAKE_CASE_RE.test(v)) {
      setIdError('ID must be snake_case')
    } else if (existingPortIds.includes(v) && v !== port?.id) {
      setIdError('Port ID must be unique within the node')
    } else {
      setIdError('')
    }
  }

  function handleSave() {
    if (!id || !SNAKE_CASE_RE.test(id)) {
      setIdError('ID must be snake_case')
      return
    }
    if (existingPortIds.includes(id) && id !== port?.id) {
      setIdError('Port ID must be unique within the node')
      return
    }
    if (!label.trim()) return

    onSave({
      id,
      label: label.trim() || id,
      type,
      required,
      cardinality,
    })
  }

  return (
    <div className="field-dialog-overlay" onClick={onClose}>
      <div className="field-dialog" onClick={(e) => e.stopPropagation()} style={{ width: 'min(420px, calc(100% - 40px))' }}>
        <h3>{isEditing ? '编辑端口' : '添加端口'} ({direction === 'input' ? '输入' : '输出'})</h3>

        <label>
          <span>ID</span>
          <input
            type="text"
            value={id}
            onChange={(e) => handleIdChange(e.target.value)}
            disabled={isEditing}
            placeholder="snake_case_port_id"
          />
          {idError && <small style={{ color: '#d47868' }}>{idError}</small>}
        </label>

        <label>
          <span>Label</span>
          <input
            type="text"
            value={label}
            onChange={(e) => handleLabelChange(e.target.value)}
            placeholder="Display name"
          />
        </label>

        <label>
          <span>Type</span>
          <select
            value={type}
            onChange={(e) => setType(e.target.value as PortType)}
          >
            {PORT_TYPES.map((t) => (
              <option key={t} value={t}>{PORT_TYPE_LABELS[t]}</option>
            ))}
          </select>
        </label>

        <label className="prop-field-row" style={{ marginBottom: 14 }}>
          <span style={{ flex: 1 }}>Required</span>
          <input
            type="checkbox"
            checked={required}
            onChange={(e) => setRequired(e.target.checked)}
          />
        </label>

        <label>
          <span>Cardinality</span>
          <select
            value={cardinality}
            onChange={(e) => setCardinality(e.target.value as Cardinality)}
          >
            {(Object.entries(CARDINALITY_LABELS) as [Cardinality, string][]).map(([val, lbl]) => (
              <option key={val} value={val}>{lbl}</option>
            ))}
          </select>
        </label>

        <div className="field-dialog-actions">
          {isEditing && onDelete && (
            <button className="field-dialog-delete" onClick={onDelete}>
              <Trash size={12} /> Delete
            </button>
          )}
          <button className="field-dialog-cancel" onClick={onClose}>Cancel</button>
          <button className="field-dialog-save" onClick={handleSave}>Save</button>
        </div>
      </div>
    </div>
  )
}
