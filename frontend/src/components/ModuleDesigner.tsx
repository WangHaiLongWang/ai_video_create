import { useState, useCallback } from 'react'
import {
  Plus,
  Trash,
  ArrowUp,
  ArrowDown,
  ArrowsLeftRight,
  Lightning,
  Package,
  Lock,
  Warning,
  Check,
  X,
  Pencil,
} from '@phosphor-icons/react'
import { useModuleDesignerStore, configFieldsToSchema, schemaToConfigFields } from '../store/moduleDesignerSlice'
import type { ModuleDefinition, ConfigSchemaField, ModuleCategory, ModuleIcon, ModulePort } from '../schemas/module-definition'
import { NODE_CATALOG } from '../schemas/node-manifest'
import type { NodeKind } from '../types'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const CATEGORIES: ModuleCategory[] = ['Input', 'LLM', 'Image', 'Video', 'Transform', 'Output']
const ICONS: ModuleIcon[] = [
  'image-square', 'video', 'type', 'code', 'chat-circle', 'lightning',
  'arrow-right', 'arrows-left-right', 'export', 'import', 'film-strip',
  'music-note', 'microphone', 'paint-brush', 'wand', 'sparkle',
]
const BASE_KINDS: NodeKind[] = ['textInput', 'storyboard', 'textToImage', 'imageToVideo', 'videoConcat', 'output']
const STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  published: 'Published',
  archived: 'Archived',
}
const STATUS_COLORS: Record<string, string> = {
  draft: '#b8a44e',
  published: '#7dce7d',
  archived: '#737a6e',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function getPortsForBaseKind(baseKind: NodeKind): { inputs: ModulePort[]; outputs: ModulePort[] } {
  const manifest = NODE_CATALOG[baseKind]
  if (!manifest) return { inputs: [], outputs: [] }
  return {
    inputs: manifest.ports.inputs.map((p) => ({
      id: p.id,
      type: p.type,
      required: p.required,
      cardinality: p.cardinality,
      label: p.label,
    })),
    outputs: manifest.ports.outputs.map((p) => ({
      id: p.id,
      type: p.type,
      required: p.required,
      cardinality: p.cardinality,
      label: p.label,
    })),
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SectionHeader({ title, icon }: { title: string; icon: React.ReactNode }) {
  return (
    <div className="md-section-header">
      {icon}
      <span>{title}</span>
    </div>
  )
}

function BasicInfoSection() {
  const { draft, updateDraft } = useModuleDesignerStore()
  if (!draft) return null

  return (
    <div className="md-section">
      <SectionHeader title="Basic Info" icon={<Package size={14} />} />
      <label className="md-field">
        <span>Module ID</span>
        <input
          type="text"
          value={draft.id}
          readOnly
          className="md-input md-input-readonly"
        />
      </label>
      <label className="md-field">
        <span>Label</span>
        <input
          type="text"
          value={draft.label}
          onChange={(e) => updateDraft({ label: e.target.value })}
          className="md-input"
        />
      </label>
      <label className="md-field">
        <span>Description</span>
        <textarea
          value={draft.description ?? ''}
          onChange={(e) => updateDraft({ description: e.target.value })}
          className="md-input md-textarea"
          rows={3}
        />
      </label>
      <label className="md-field">
        <span>Category</span>
        <select
          value={draft.category}
          onChange={(e) => updateDraft({ category: e.target.value })}
          className="md-input"
        >
          {CATEGORIES.map((cat) => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
      </label>
      <label className="md-field">
        <span>Icon</span>
        <select
          value={draft.icon ?? 'image-square'}
          onChange={(e) => updateDraft({ icon: e.target.value as ModuleIcon })}
          className="md-input"
        >
          {ICONS.map((icon) => (
            <option key={icon} value={icon}>{icon}</option>
          ))}
        </select>
      </label>
      <label className="md-field">
        <span>Status</span>
        <div className="md-status-badge" style={{ color: STATUS_COLORS[draft.status] }}>
          {STATUS_LABELS[draft.status]}
        </div>
      </label>
    </div>
  )
}

function ExecutionSection() {
  const { draft, updateDraft } = useModuleDesignerStore()
  if (!draft) return null

  return (
    <div className="md-section">
      <SectionHeader title="Execution" icon={<Lightning size={14} />} />
      <label className="md-field">
        <span>Base Kind</span>
        <select
          value={draft.baseKind}
          onChange={(e) => updateDraft({ baseKind: e.target.value as NodeKind })}
          className="md-input"
        >
          {BASE_KINDS.map((kind) => (
            <option key={kind} value={kind}>{kind}</option>
          ))}
        </select>
        <span className="md-hint">Determines which Handler the module reuses</span>
      </label>
    </div>
  )
}

function ProviderPolicySection() {
  const { draft, updateDraft } = useModuleDesignerStore()
  if (!draft) return null

  const { providerPolicy } = draft

  const toggleAllowed = useCallback((provider: string) => {
    const allowed = providerPolicy.allowed.includes(provider)
      ? providerPolicy.allowed.filter((p) => p !== provider)
      : [...providerPolicy.allowed, provider]
    updateDraft({
      providerPolicy: {
        ...providerPolicy,
        allowed,
        default: allowed.includes(providerPolicy.default ?? '') ? providerPolicy.default : allowed[0],
      },
    })
  }, [providerPolicy, updateDraft])

  const setDefault = useCallback((provider: string) => {
    updateDraft({
      providerPolicy: { ...providerPolicy, default: provider },
    })
  }, [providerPolicy, updateDraft])

  const toggleLocked = useCallback(() => {
    updateDraft({
      providerPolicy: { ...providerPolicy, locked: !providerPolicy.locked },
    })
  }, [providerPolicy, updateDraft])

  const setCapability = useCallback((capability: string) => {
    updateDraft({
      providerPolicy: { ...providerPolicy, capability },
    })
  }, [providerPolicy, updateDraft])

  // Provider options based on capability
  const providerOptions: Record<string, string[]> = {
    image: ['doubao', 'openai', 'midjourney', 'stable-diffusion'],
    video: ['kling', 'pika', 'runway', 'doubao'],
    text: ['openai', 'anthropic', 'doubao', 'moonshot'],
  }

  const availableProviders = providerOptions[providerPolicy.capability] ?? []

  return (
    <div className="md-section">
      <SectionHeader title="Provider Policy" icon={<Lock size={14} />} />
      <label className="md-field">
        <span>Capability</span>
        <select
          value={providerPolicy.capability}
          onChange={(e) => setCapability(e.target.value)}
          className="md-input"
        >
          <option value="image">image</option>
          <option value="video">video</option>
          <option value="text">text</option>
        </select>
      </label>
      <label className="md-field">
        <span>Allowed Providers</span>
        <div className="md-checkbox-group">
          {availableProviders.map((provider) => (
            <label key={provider} className="md-checkbox-label">
              <input
                type="checkbox"
                checked={providerPolicy.allowed.includes(provider)}
                onChange={() => toggleAllowed(provider)}
              />
              {provider}
            </label>
          ))}
        </div>
      </label>
      {providerPolicy.allowed.length > 0 && (
        <label className="md-field">
          <span>Default Provider</span>
          <select
            value={providerPolicy.default ?? providerPolicy.allowed[0] ?? ''}
            onChange={(e) => setDefault(e.target.value)}
            className="md-input"
          >
            {providerPolicy.allowed.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </label>
      )}
      <label className="md-field md-field-row">
        <span>Locked</span>
        <button
          type="button"
          className={`md-toggle ${providerPolicy.locked ? 'md-toggle-on' : ''}`}
          onClick={toggleLocked}
          aria-label="Toggle provider lock"
        >
          <Lock size={12} />
          {providerPolicy.locked ? 'Locked' : 'Unlocked'}
        </button>
      </label>
    </div>
  )
}

function ConfigSchemaSection() {
  const { draft, addConfigField, updateConfigField, removeConfigField, reorderConfigFields } = useModuleDesignerStore()
  const [editingKey, setEditingKey] = useState<string | null>(null)

  if (!draft) return null

  const fields = schemaToConfigFields(draft.configSchema as Record<string, unknown> | undefined)

  const handleAddField = () => {
    const newField: ConfigSchemaField = {
      key: `field_${fields.length + 1}`,
      type: 'string',
      title: `Field ${fields.length + 1}`,
      required: false,
      format: 'text',
    }
    addConfigField(newField)
    setEditingKey(newField.key)
  }

  const handleFieldChange = (oldKey: string, partial: Partial<ConfigSchemaField>) => {
    const field = fields.find((f) => f.key === oldKey)
    if (!field) return
    updateConfigField(oldKey, { ...field, ...partial })
  }

  const handleRemoveField = (key: string) => {
    removeConfigField(key)
    if (editingKey === key) setEditingKey(null)
  }

  const handleReorder = (fromIndex: number, toIndex: number) => {
    reorderConfigFields(fromIndex, toIndex)
  }

  return (
    <div className="md-section">
      <SectionHeader title="Config Schema" icon={<Pencil size={14} />} />
      <div className="md-field-list">
        {fields.map((field, idx) => (
          <div key={field.key} className="md-field-item">
            <div className="md-field-item-header">
              <span className="md-field-item-key">{field.key}</span>
              <span className="md-field-item-type">{field.type}</span>
              <div className="md-field-item-actions">
                <button
                  onClick={() => handleReorder(idx, idx - 1)}
                  disabled={idx === 0}
                  title="Move up"
                  className="md-icon-btn"
                >
                  <ArrowUp size={11} />
                </button>
                <button
                  onClick={() => handleReorder(idx, idx + 1)}
                  disabled={idx === fields.length - 1}
                  title="Move down"
                  className="md-icon-btn"
                >
                  <ArrowDown size={11} />
                </button>
                <button
                  onClick={() => setEditingKey(editingKey === field.key ? null : field.key)}
                  title="Edit"
                  className="md-icon-btn"
                >
                  <Pencil size={11} />
                </button>
                <button
                  onClick={() => handleRemoveField(field.key)}
                  title="Remove"
                  className="md-icon-btn md-icon-btn-danger"
                >
                  <Trash size={11} />
                </button>
              </div>
            </div>

            {editingKey === field.key && (
              <div className="md-field-item-editor">
                <label className="md-field">
                  <span>Key</span>
                  <input
                    type="text"
                    value={field.key}
                    onChange={(e) => handleFieldChange(field.key, { key: e.target.value })}
                    className="md-input"
                  />
                </label>
                <label className="md-field">
                  <span>Title</span>
                  <input
                    type="text"
                    value={field.title}
                    onChange={(e) => handleFieldChange(field.key, { title: e.target.value })}
                    className="md-input"
                  />
                </label>
                <label className="md-field">
                  <span>Type</span>
                  <select
                    value={field.type}
                    onChange={(e) => handleFieldChange(field.key, { type: e.target.value as ConfigSchemaField['type'] })}
                    className="md-input"
                  >
                    <option value="string">string</option>
                    <option value="integer">integer</option>
                    <option value="number">number</option>
                    <option value="boolean">boolean</option>
                    <option value="enum">enum</option>
                  </select>
                </label>
                {field.type === 'string' && (
                  <label className="md-field">
                    <span>Format</span>
                    <select
                      value={field.format ?? 'text'}
                      onChange={(e) => handleFieldChange(field.key, { format: e.target.value as 'text' | 'textarea' })}
                      className="md-input"
                    >
                      <option value="text">text</option>
                      <option value="textarea">textarea</option>
                    </select>
                  </label>
                )}
                {(field.type === 'integer' || field.type === 'number') && (
                  <>
                    <label className="md-field">
                      <span>Minimum</span>
                      <input
                        type="number"
                        value={field.minimum ?? ''}
                        onChange={(e) => handleFieldChange(field.key, { minimum: e.target.value === '' ? undefined : Number(e.target.value) })}
                        className="md-input"
                      />
                    </label>
                    <label className="md-field">
                      <span>Maximum</span>
                      <input
                        type="number"
                        value={field.maximum ?? ''}
                        onChange={(e) => handleFieldChange(field.key, { maximum: e.target.value === '' ? undefined : Number(e.target.value) })}
                        className="md-input"
                      />
                    </label>
                  </>
                )}
                {field.type === 'enum' && (
                  <label className="md-field">
                    <span>Options (comma-separated)</span>
                    <input
                      type="text"
                      value={field.enumOptions?.join(', ') ?? ''}
                      onChange={(e) => handleFieldChange(field.key, { enumOptions: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
                      className="md-input"
                      placeholder="option1, option2, option3"
                    />
                  </label>
                )}
                <label className="md-field">
                  <span>Default</span>
                  <input
                    type={field.type === 'boolean' ? 'checkbox' : field.type === 'integer' || field.type === 'number' ? 'number' : 'text'}
                    checked={field.type === 'boolean' ? Boolean(field.default) : undefined}
                    value={field.type === 'boolean' ? undefined : (field.default as string | number | undefined) ?? ''}
                    onChange={(e) => {
                      if (field.type === 'boolean') {
                        handleFieldChange(field.key, { default: e.target.checked })
                      } else if (field.type === 'integer' || field.type === 'number') {
                        handleFieldChange(field.key, { default: e.target.value === '' ? undefined : Number(e.target.value) })
                      } else {
                        handleFieldChange(field.key, { default: e.target.value })
                      }
                    }}
                    className="md-input"
                  />
                </label>
                <label className="md-field md-field-row">
                  <span>Required</span>
                  <input
                    type="checkbox"
                    checked={field.required}
                    onChange={(e) => handleFieldChange(field.key, { required: e.target.checked })}
                  />
                </label>
              </div>
            )}
          </div>
        ))}
      </div>
      <button className="md-add-field-btn" onClick={handleAddField}>
        <Plus size={12} /> Add Field
      </button>
    </div>
  )
}

function PortsSection() {
  const { draft } = useModuleDesignerStore()
  if (!draft) return null

  const ports = getPortsForBaseKind(draft.baseKind as NodeKind)

  return (
    <div className="md-section">
      <SectionHeader title="Ports (Read-only)" icon={<ArrowsLeftRight size={14} />} />
      <div className="md-ports-group">
        <span className="md-ports-label">Inputs</span>
        {ports.inputs.length === 0 ? (
          <span className="md-ports-empty">No inputs</span>
        ) : (
          ports.inputs.map((p) => (
            <div key={p.id} className="md-port-item">
              <span className="md-port-id">{p.id}</span>
              <span className="md-port-type">{p.type}</span>
              {p.required && <span className="md-port-required">*</span>}
            </div>
          ))
        )}
      </div>
      <div className="md-ports-group">
        <span className="md-ports-label">Outputs</span>
        {ports.outputs.length === 0 ? (
          <span className="md-ports-empty">No outputs</span>
        ) : (
          ports.outputs.map((p) => (
            <div key={p.id} className="md-port-item">
              <span className="md-port-id">{p.id}</span>
              <span className="md-port-type">{p.type}</span>
              {p.required && <span className="md-port-required">*</span>}
            </div>
          ))
        )}
      </div>
      <div className="md-ports-warning">
        <Warning size={12} />
        <span>Core ports are derived from baseKind and cannot be edited. Extension ports can be added but must be bound to publish.</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------
export function ModuleDesigner() {
  const { isOpen, draft, isDirty, closeDesigner, saveDraft, publishDraft } = useModuleDesignerStore()
  const [saving, setSaving] = useState(false)
  const [publishing, setPublishing] = useState(false)

  if (!isOpen || !draft) return null

  const handleClose = () => {
    if (isDirty) {
      if (window.confirm('You have unsaved changes. Are you sure you want to close?')) {
        closeDesigner()
      }
    } else {
      closeDesigner()
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await saveDraft()
    } catch {
      // Error handled in store
    } finally {
      setSaving(false)
    }
  }

  const handlePublish = async () => {
    setPublishing(true)
    try {
      await publishDraft()
    } catch {
      // Error handled in store
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div className="md-overlay">
      <div className="md-panel">
        <div className="md-header">
          <div className="md-header-title">
            <Package size={16} />
            <span>{draft.id ? 'Edit Module' : 'Create Module'}</span>
          </div>
          <div className="md-header-actions">
            <button
              className="md-btn md-btn-secondary"
              onClick={handleClose}
              aria-label="Close"
            >
              <X size={14} />
            </button>
          </div>
        </div>

        <div className="md-body">
          <BasicInfoSection />
          <ExecutionSection />
          <ProviderPolicySection />
          <ConfigSchemaSection />
          <PortsSection />
        </div>

        <div className="md-footer">
          <button
            className="md-btn md-btn-secondary"
            onClick={handleClose}
          >
            Cancel
          </button>
          <button
            className="md-btn md-btn-primary"
            onClick={handleSave}
            disabled={saving || !isDirty}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
          <button
            className="md-btn md-btn-success"
            onClick={handlePublish}
            disabled={publishing}
          >
            {publishing ? 'Publishing...' : 'Publish'}
          </button>
        </div>
      </div>
    </div>
  )
}
