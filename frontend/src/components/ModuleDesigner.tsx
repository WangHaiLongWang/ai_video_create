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
  Copy,
  ArchiveBox,
} from '@phosphor-icons/react'
import { useModuleDesignerStore, configFieldsToSchema, schemaToConfigFields } from '../store/moduleDesignerSlice'
import type { ModuleDefinition, ConfigSchemaField, ModuleCategory, ModuleIcon, ModulePort } from '../schemas/module-definition'
import { collectPublishBlockers } from '../schemas/module-definition'
import { NODE_CATALOG } from '../schemas/node-manifest'
import type { NodeKind } from '../types'
import { cloneModule, archiveModule } from '../api/modules'
import { PortEditorDialog } from './PortEditorDialog'
import type { PortEditorPortSave } from './PortEditorDialog'

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
/** Core port ids from the baseKind manifest (locked by the module contract). */
function getCorePortIds(baseKind: string): { inputs: Set<string>; outputs: Set<string> } {
  const manifest = NODE_CATALOG[baseKind as NodeKind]
  return {
    inputs: new Set((manifest?.ports.inputs ?? []).map((p) => p.id)),
    outputs: new Set((manifest?.ports.outputs ?? []).map((p) => p.id)),
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
  const { draft, addExtendedPort, updateExtendedPort, deleteExtendedPort } = useModuleDesignerStore()
  const [dialog, setDialog] = useState<{ direction: 'input' | 'output'; port: ModulePort | null } | null>(null)

  if (!draft) return null

  const coreIds = getCorePortIds(draft.baseKind)
  const configKeys = schemaToConfigFields(draft.configSchema as Record<string, unknown> | undefined).map((f) => f.key)
  const blockers = collectPublishBlockers(draft.ports, draft.baseKind)
  const blockerByField = new Map(blockers.map((b) => [b.field, b]))

  const keyFor = (direction: 'input' | 'output'): 'inputs' | 'outputs' =>
    direction === 'input' ? 'inputs' : 'outputs'

  const handleSavePort = (saved: PortEditorPortSave) => {
    if (!dialog) return
    const port: ModulePort = {
      id: saved.id,
      type: saved.type as ModulePort['type'],
      required: saved.required,
      cardinality: saved.cardinality,
      label: saved.label,
      binding: saved.binding,
    }
    if (dialog.port) {
      updateExtendedPort(dialog.direction, dialog.port.id, port)
    } else {
      addExtendedPort(dialog.direction, port)
    }
    setDialog(null)
  }

  const renderPort = (direction: 'input' | 'output', port: ModulePort, index: number) => {
    const listKey = keyFor(direction)
    const isCore = coreIds[listKey].has(port.id)
    const blocker = blockerByField.get(`ports.${listKey}[${index}].binding`)
    return (
      <div key={port.id} className={`md-port-item${blocker ? ' md-port-item-unbound' : ''}`}>
        {isCore && (
          <span className="md-port-lock" title="Core port (locked by baseKind)">
            <Lock size={11} />
          </span>
        )}
        <span className="md-port-id" title={port.label && port.label !== port.id ? port.label : undefined}>
          {port.id}
        </span>
        <span className="md-port-type">{port.type}</span>
        {port.required && <span className="md-port-required">*</span>}
        <span className="md-port-type">{port.cardinality === 'many' ? '0..*' : '1'}</span>
        {isCore ? (
          <span className="md-port-binding md-port-binding-core">core</span>
        ) : port.binding ? (
          <span className="md-port-binding md-port-binding-bound" title={`Bound to config.${port.binding}`}>
            → {port.binding}
          </span>
        ) : (
          <span className="md-port-binding md-port-binding-unbound">未绑定</span>
        )}
        <div className="md-port-item-actions">
          <button
            onClick={() => setDialog({ direction, port })}
            title={isCore ? 'Edit label' : 'Edit port'}
            className="md-icon-btn"
          >
            <Pencil size={11} />
          </button>
          {!isCore && (
            <button
              onClick={() => deleteExtendedPort(direction, port.id)}
              title="Delete port"
              className="md-icon-btn md-icon-btn-danger"
            >
              <Trash size={11} />
            </button>
          )}
        </div>
        {blocker && (
          <div className="md-port-error">
            <Warning size={10} />
            <span>{blocker.message}</span>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="md-section">
      <SectionHeader title="Ports" icon={<ArrowsLeftRight size={14} />} />
      <div className="md-ports-group">
        <div className="md-ports-group-header">
          <span className="md-ports-label">Inputs</span>
          <button
            onClick={() => setDialog({ direction: 'input', port: null })}
            title="Add input port"
            className="md-icon-btn"
          >
            <Plus size={11} />
          </button>
        </div>
        {draft.ports.inputs.length === 0 ? (
          <span className="md-ports-empty">No inputs</span>
        ) : (
          draft.ports.inputs.map((p, i) => renderPort('input', p, i))
        )}
      </div>
      <div className="md-ports-group">
        <div className="md-ports-group-header">
          <span className="md-ports-label">Outputs</span>
          <button
            onClick={() => setDialog({ direction: 'output', port: null })}
            title="Add output port"
            className="md-icon-btn"
          >
            <Plus size={11} />
          </button>
        </div>
        {draft.ports.outputs.length === 0 ? (
          <span className="md-ports-empty">No outputs</span>
        ) : (
          draft.ports.outputs.map((p, i) => renderPort('output', p, i))
        )}
      </div>
      {dialog && (() => {
        const listKey = keyFor(dialog.direction)
        const editingCore = dialog.port != null && coreIds[listKey].has(dialog.port.id)
        return (
          <PortEditorDialog
            direction={dialog.direction}
            port={dialog.port}
            existingPortIds={draft.ports[listKey].map((p) => p.id)}
            bindingMode={editingCore ? undefined : { value: dialog.port?.binding, options: configKeys }}
            lockContract={editingCore}
            onSave={handleSavePort}
            onDelete={
              dialog.port && !editingCore
                ? () => {
                    deleteExtendedPort(dialog.direction, dialog.port!.id)
                    setDialog(null)
                  }
                : undefined
            }
            onClose={() => setDialog(null)}
          />
        )
      })()}
      <div className="md-ports-warning">
        <Warning size={12} />
        <span>
          Core ports are locked to the baseKind contract (id / type / cardinality); only the label may be overridden.
          Extended ports must be bound to a config field before the module can be published or executed.
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------
export function ModuleDesigner() {
  const { isOpen, draft, isDirty, expectedVersion, error, validationErrors, closeDesigner, saveDraft, publishDraft, openDesigner } = useModuleDesignerStore()
  const [saving, setSaving] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [cloning, setCloning] = useState(false)
  const [archiving, setArchiving] = useState(false)

  if (!isOpen || !draft) return null

  // Client-side mirror of the UNBOUND_MODULE_PORT publish gate.
  const publishBlockers = collectPublishBlockers(draft.ports, draft.baseKind)

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

  const handleClone = async () => {
    if (!draft.id) return
    setCloning(true)
    try {
      const cloned = await cloneModule(draft.id, draft.version, expectedVersion)
      // Open the cloned module in the designer
      closeDesigner()
      openDesigner(cloned.id, cloned)
    } catch (err) {
      console.error('Failed to clone module:', err)
    } finally {
      setCloning(false)
    }
  }

  const handleArchive = async () => {
    if (!draft.id) return
    if (!window.confirm('Are you sure you want to archive this module?')) return
    setArchiving(true)
    try {
      const archived = await archiveModule(draft.id, draft.version, expectedVersion)
      closeDesigner()
      openDesigner(archived.id, archived)
    } catch (err) {
      console.error('Failed to archive module:', err)
    } finally {
      setArchiving(false)
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
          {error && (
            <div className="md-ports-warning" role="alert">
              <Warning size={12} />
              <div className="md-error-detail">
                {validationErrors && validationErrors.length > 0 ? (
                  <ul className="md-error-list">
                    {validationErrors.map((e, i) => (
                      <li key={`${e.field}-${i}`}>
                        <strong>{e.error}</strong> <code>{e.field}</code>: {e.message}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span>{error}</span>
                )}
              </div>
            </div>
          )}
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
          <div className="md-footer-spacer" />
          {draft.id && (
            <>
              <button
                className="md-btn md-btn-secondary"
                onClick={handleClone}
                disabled={cloning}
                title="Clone module"
              >
                <Copy size={12} />
                {cloning ? 'Cloning...' : 'Clone'}
              </button>
              <button
                className="md-btn md-btn-secondary"
                onClick={handleArchive}
                disabled={archiving || draft.status === 'archived'}
                title="Archive module"
              >
                <ArchiveBox size={12} />
                {archiving ? 'Archiving...' : 'Archive'}
              </button>
            </>
          )}
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
            disabled={publishing || publishBlockers.length > 0}
            title={
              publishBlockers.length > 0
                ? publishBlockers.map((b) => b.message).join('\n')
                : undefined
            }
          >
            {publishing ? 'Publishing...' : 'Publish'}
          </button>
        </div>
      </div>
    </div>
  )
}
