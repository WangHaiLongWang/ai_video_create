import { useState } from 'react'
import type { FieldDefinition, FieldType, FieldOption } from '../types'
import { Plus, Trash } from '@phosphor-icons/react'

const FIELD_TYPE_LABELS: Record<FieldType, string> = {
  text: 'Text',
  textarea: 'Textarea',
  number: 'Number',
  boolean: 'Boolean',
  select: 'Select',
  multi_select: 'Multi Select',
  json: 'JSON',
  prompt: 'Prompt',
}

const SNAKE_CASE_RE = /^[a-z][a-z0-9]*(_[a-z0-9]+)*$/

function toSnakeCase(s: string): string {
  return s
    .replace(/([A-Z])/g, '_$1')
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, '')
    .replace(/^_/, '')
    .replace(/_+/g, '_')
}

export interface FieldEditorDialogProps {
  field?: FieldDefinition | null  // null = add new
  onSave: (field: FieldDefinition) => void
  onDelete?: () => void
  onClose: () => void
}

export function FieldEditorDialog({ field, onSave, onDelete, onClose }: FieldEditorDialogProps) {
  const isEditing = field != null

  const [id, setId] = useState(field?.id ?? '')
  const [label, setLabel] = useState(field?.label ?? '')
  const [type, setType] = useState<FieldType>(field?.type ?? 'text')
  const [description, setDescription] = useState(field?.description ?? '')
  const [required, setRequired] = useState(field?.required ?? false)
  const [defaultValue, setDefaultValue] = useState<string>(
    field?.default != null ? String(field.default) : '',
  )
  const [options, setOptions] = useState<FieldOption[]>(field?.options ?? [])
  const [advanced, setAdvanced] = useState(field?.advanced ?? false)
  const [idError, setIdError] = useState('')

  function handleLabelChange(v: string) {
    setLabel(v)
    if (!isEditing) {
      const snake = toSnakeCase(v)
      setId(snake)
      if (!SNAKE_CASE_RE.test(snake)) {
        setIdError('ID must be snake_case')
      } else {
        setIdError('')
      }
    }
  }

  function handleIdChange(v: string) {
    setId(v)
    if (!SNAKE_CASE_RE.test(v)) {
      setIdError('ID must be snake_case')
    } else {
      setIdError('')
    }
  }

  function handleAddOption() {
    setOptions([...options, { label: '', value: '' }])
  }

  function handleOptionChange(index: number, key: 'label' | 'value', val: string) {
    const next = [...options]
    next[index] = { ...next[index], [key]: val }
    setOptions(next)
  }

  function handleRemoveOption(index: number) {
    setOptions(options.filter((_, i) => i !== index))
  }

  function handleSave() {
    if (!id || !SNAKE_CASE_RE.test(id)) {
      setIdError('ID must be snake_case')
      return
    }
    if (!label.trim()) return

    const parsedDefault: string | number | boolean | undefined =
      type === 'number' && defaultValue !== '' ? Number(defaultValue) :
      type === 'boolean' ? (defaultValue === 'true' || defaultValue === '1') :
      defaultValue !== '' ? defaultValue : undefined

    const result: FieldDefinition = {
      id,
      label: label.trim(),
      type,
      description: description.trim() || undefined,
      required: required || undefined,
      default: parsedDefault,
      advanced: advanced || undefined,
    }
    if ((type === 'select' || type === 'multi_select') && options.length > 0) {
      result.options = options.filter((o) => o.label.trim() !== '')
    }
    onSave(result)
  }

  const needsOptions = type === 'select' || type === 'multi_select'
  const isNumber = type === 'number'
  const isBoolean = type === 'boolean'

  return (
    <div className="field-dialog-overlay" onClick={onClose}>
      <div className="field-dialog" onClick={(e) => e.stopPropagation()}>
        <h3>{isEditing ? '编辑字段' : '添加字段'}</h3>

        <label>
          <span>ID</span>
          <input
            type="text"
            value={id}
            onChange={(e) => handleIdChange(e.target.value)}
            placeholder="snake_case_field_id"
          />
          {idError && <small style={{ color: '#d47868' }}>{idError}</small>}
          {isEditing && field && id !== field.id && (
            <small style={{ color: '#8ba87a', display: 'block', marginTop: 2 }}>
              Rename from "{field.id}" — config value will be migrated
            </small>
          )}
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
            onChange={(e) => setType(e.target.value as FieldType)}
          >
            {Object.entries(FIELD_TYPE_LABELS).map(([val, lbl]) => (
              <option key={val} value={val}>{lbl}</option>
            ))}
          </select>
        </label>

        <label>
          <span>Description</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
          />
        </label>

        <label className="prop-field-row" style={{ marginBottom: 14 }}>
          <span style={{ flex: 1 }}>Required</span>
          <input
            type="checkbox"
            checked={required}
            onChange={(e) => setRequired(e.target.checked)}
          />
        </label>

        {!isBoolean && (
          <label>
            <span>Default value</span>
            {isNumber ? (
              <input
                type="number"
                value={defaultValue}
                onChange={(e) => setDefaultValue(e.target.value)}
              />
            ) : (
              <input
                type="text"
                value={defaultValue}
                onChange={(e) => setDefaultValue(e.target.value)}
              />
            )}
          </label>
        )}

        {isBoolean && (
          <label>
            <span>Default value</span>
            <select
              value={defaultValue || ''}
              onChange={(e) => setDefaultValue(e.target.value)}
            >
              <option value="">None</option>
              <option value="true">True</option>
              <option value="false">False</option>
            </select>
          </label>
        )}

        {needsOptions && (
          <div style={{ marginBottom: 14 }}>
            <span style={{ fontSize: 10, color: '#9ca397', display: 'block', marginBottom: 6 }}>Options</span>
            {options.map((opt, i) => (
              <div className="option-row" key={i}>
                <input
                  type="text"
                  placeholder="Label"
                  value={opt.label}
                  onChange={(e) => handleOptionChange(i, 'label', e.target.value)}
                />
                <input
                  type="text"
                  placeholder="Value"
                  value={opt.value}
                  onChange={(e) => handleOptionChange(i, 'value', e.target.value)}
                />
                <button onClick={() => handleRemoveOption(i)}>
                  <Trash size={12} />
                </button>
              </div>
            ))}
            <button
              type="button"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                border: 0,
                background: 'transparent',
                color: 'var(--accent)',
                fontSize: 11,
                cursor: 'pointer',
                padding: '4px 0',
              }}
              onClick={handleAddOption}
            >
              <Plus size={12} /> Add option
            </button>
          </div>
        )}

        <label className="prop-field-row" style={{ marginBottom: 0 }}>
          <span style={{ flex: 1 }}>Advanced</span>
          <input
            type="checkbox"
            checked={advanced}
            onChange={(e) => setAdvanced(e.target.checked)}
          />
        </label>

        <div className="field-dialog-actions">
          {isEditing && onDelete && (
            <button className="field-dialog-delete" onClick={onDelete}>Delete</button>
          )}
          <button className="field-dialog-cancel" onClick={onClose}>Cancel</button>
          <button className="field-dialog-save" onClick={handleSave}>Save</button>
        </div>
      </div>
    </div>
  )
}
