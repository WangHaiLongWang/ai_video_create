import { create } from 'zustand'
import type { ModuleDefinition, ModuleDesignerState, ConfigSchemaField, ModulePort, PortError } from '../schemas/module-definition'
import { createModule, publishModule, updateModule, ModuleApiError } from '../api/modules'
import { NODE_CATALOG } from '../schemas/node-manifest'
import type { NodeKind } from '../types'

type PortDirection = 'input' | 'output'
type PortKey = 'inputs' | 'outputs'

function directionKey(direction: PortDirection): PortKey {
  return direction === 'input' ? 'inputs' : 'outputs'
}

function getPortsForKind(baseKind: string): { inputs: ModulePort[]; outputs: ModulePort[] } {
  const manifest = NODE_CATALOG[baseKind as NodeKind]
  if (!manifest) return { inputs: [], outputs: [] }
  return {
    inputs: manifest.ports.inputs.map((port) => ({ ...port })),
    outputs: manifest.ports.outputs.map((port) => ({ ...port })),
  }
}

/** Core port ids (from the baseKind manifest) per direction. */
function corePortIds(baseKind: string): { inputs: Set<string>; outputs: Set<string> } {
  const manifest = NODE_CATALOG[baseKind as NodeKind]
  return {
    inputs: new Set((manifest?.ports.inputs ?? []).map((p) => p.id)),
    outputs: new Set((manifest?.ports.outputs ?? []).map((p) => p.id)),
  }
}

/**
 * Merge ports when baseKind changes: take the new kind's core ports and keep
 * the user-added extended ports. An extended port whose id collides with a
 * new core id loses (core wins); old core ports that left the contract drop.
 */
function mergePortsForBaseKind(
  prevKind: string,
  prevPorts: { inputs: ModulePort[]; outputs: ModulePort[] },
  nextKind: string,
): { inputs: ModulePort[]; outputs: ModulePort[] } {
  const prevCore = corePortIds(prevKind)
  const nextCore = corePortIds(nextKind)
  const next = getPortsForKind(nextKind)

  const keptExtensions = (prev: ModulePort[], wasCore: Set<string>, isCore: Set<string>) =>
    prev.filter((p) => !wasCore.has(p.id) && !isCore.has(p.id))

  return {
    inputs: [...next.inputs, ...keptExtensions(prevPorts.inputs, prevCore.inputs, nextCore.inputs)],
    outputs: [...next.outputs, ...keptExtensions(prevPorts.outputs, prevCore.outputs, nextCore.outputs)],
  }
}

/** Surface structured API errors (ModuleApiError.errors) when present. */
function toErrorState(err: unknown, fallback: string): { error: string; validationErrors?: PortError[] } {
  if (err instanceof ModuleApiError) {
    return { error: err.message, validationErrors: err.errors }
  }
  return { error: err instanceof Error ? err.message : fallback }
}

// ---------------------------------------------------------------------------
// Helper: auto-generate module ID from label
// ---------------------------------------------------------------------------
function generateModuleId(label: string, category: string): string {
  const slug = label
    .toLowerCase()
    .replace(/[^a-z0-9一-鿿]+/g, '-')
    .replace(/^-|-$/g, '')
  return `${category.toLowerCase()}.${slug || 'unnamed'}`
}

// ---------------------------------------------------------------------------
// Helper: create empty draft
// ---------------------------------------------------------------------------
function createEmptyDraft(): ModuleDefinition {
  return {
    id: 'custom.new-module',
    version: '0.1.0',
    status: 'draft',
    baseKind: 'textToImage',
    category: 'Image',
    label: 'New Module',
    description: '',
    icon: 'image-square',
    providerPolicy: {
      capability: 'image',
      allowed: [],
      default: undefined,
      locked: false,
    },
    configSchema: {
      type: 'object',
      properties: {},
    },
    defaultConfig: {},
    ports: getPortsForKind('textToImage'),
    metadata: {},
  }
}

// ---------------------------------------------------------------------------
// Convert ConfigSchemaField[] to JSON Schema properties
// ---------------------------------------------------------------------------
export function configFieldsToSchema(fields: ConfigSchemaField[]): Record<string, unknown> {
  const properties: Record<string, unknown> = {}
  for (const field of fields) {
    const prop: Record<string, unknown> = {
      type: field.type === 'integer' ? 'integer' : field.type === 'number' ? 'number' : field.type === 'boolean' ? 'boolean' : 'string',
      title: field.title,
    }
    if (field.default !== undefined) {
      prop.default = field.default
    }
    if (field.type === 'enum' && field.enumOptions) {
      prop.enum = field.enumOptions
      prop.type = 'string'
    }
    if (field.type === 'string' && field.format) {
      prop.format = field.format
    }
    if (field.minimum !== undefined) {
      prop.minimum = field.minimum
    }
    if (field.maximum !== undefined) {
      prop.maximum = field.maximum
    }
    properties[field.key] = prop
  }
  return properties
}

// ---------------------------------------------------------------------------
// Convert JSON Schema properties to ConfigSchemaField[]
// ---------------------------------------------------------------------------
export function schemaToConfigFields(schema: Record<string, unknown> | undefined): ConfigSchemaField[] {
  if (!schema) return []
  const properties = (schema as { properties?: Record<string, unknown> }).properties
  if (!properties) return []

  return Object.entries(properties).map(([key, prop]) => {
    const p = prop as Record<string, unknown>
    const type = p.enum ? 'enum' : (p.type as string) === 'integer' ? 'integer' : (p.type as string) === 'number' ? 'number' : (p.type as string) === 'boolean' ? 'boolean' : 'string'
    return {
      key,
      type: type as ConfigSchemaField['type'],
      title: (p.title as string) ?? key,
      default: p.default as string | number | boolean | undefined,
      required: false,
      enumOptions: p.enum as string[] | undefined,
      format: p.format as 'text' | 'textarea' | undefined,
      minimum: p.minimum as number | undefined,
      maximum: p.maximum as number | undefined,
    }
  })
}

// ---------------------------------------------------------------------------
// Store interface
// ---------------------------------------------------------------------------
interface ModuleDesignerActions {
  openDesigner: (moduleId?: string, module?: ModuleDefinition) => void
  updateDraft: (partial: Partial<ModuleDefinition>) => void
  saveDraft: () => Promise<void>
  publishDraft: () => Promise<void>
  closeDesigner: () => void
  addConfigField: (field: ConfigSchemaField) => void
  updateConfigField: (key: string, field: ConfigSchemaField) => void
  removeConfigField: (key: string) => void
  reorderConfigFields: (fromIndex: number, toIndex: number) => void
  /** Add a user-defined extended port (never shadows a core port id). */
  addExtendedPort: (direction: PortDirection, port: ModulePort) => void
  /**
   * Update a port by id. Extended ports accept the full update; core ports
   * only accept a `label` change (id/type/cardinality are locked by the
   * baseKind contract).
   */
  updateExtendedPort: (direction: PortDirection, id: string, port: ModulePort) => void
  /** Delete an extended port. Core ports are never deleted. */
  deleteExtendedPort: (direction: PortDirection, id: string) => void
  /** Set or clear (undefined/empty) the config-field binding on a port. */
  setPortBinding: (direction: PortDirection, id: string, binding?: string) => void
}

type ModuleDesignerStore = ModuleDesignerState & ModuleDesignerActions

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------
export const useModuleDesignerStore = create<ModuleDesignerStore>((set, get) => ({
  isOpen: false,
  moduleId: null,
  draft: null,
  isDirty: false,
  expectedVersion: 1,
  error: null,

  openDesigner: (moduleId?: string, module?: ModuleDefinition) => {
    if (module) {
      set({
        isOpen: true,
        moduleId: module.id,
        draft: { ...module },
        isDirty: false,
        expectedVersion: module.expectedVersion ?? 1,
        error: null,
      })
    } else {
      const draft = createEmptyDraft()
      if (moduleId) {
        draft.id = moduleId
      }
      set({ isOpen: true, moduleId: null, draft, isDirty: false, expectedVersion: 1, error: null })
    }
  },

  updateDraft: (partial) => {
    const { draft } = get()
    if (!draft) return
    const newDraft = { ...draft, ...partial }

    if (partial.baseKind !== undefined && partial.baseKind !== draft.baseKind) {
      // Refresh core ports from the new contract but keep extended ports.
      newDraft.ports = mergePortsForBaseKind(draft.baseKind, draft.ports, partial.baseKind)
    }

    // Auto-update ID from label if creating new
    if (partial.label !== undefined && get().moduleId === null) {
      newDraft.id = generateModuleId(partial.label, newDraft.category)
    }

    set({ draft: newDraft, isDirty: true, error: null, validationErrors: undefined })
  },

  saveDraft: async () => {
    const { draft, moduleId, expectedVersion } = get()
    if (!draft) return
    try {
      const saved = moduleId === null
        ? await createModule(draft)
        : await updateModule(draft, expectedVersion)
      set({
        moduleId: saved.id,
        draft: saved,
        isDirty: false,
        expectedVersion: saved.expectedVersion ?? (moduleId === null ? 1 : expectedVersion + 1),
        error: null,
        validationErrors: undefined,
      })
    } catch (err) {
      set(toErrorState(err, 'Failed to save module'))
      throw err
    }
  },

  publishDraft: async () => {
    const { draft } = get()
    if (!draft) return
    try {
      // Save first if dirty
      if (get().isDirty) {
        await get().saveDraft()
      }
      const current = get().draft
      if (!current) return
      const published = await publishModule(current.id, current.version, get().expectedVersion)
      set({
        draft: published,
        expectedVersion: published.expectedVersion ?? get().expectedVersion + 1,
        isDirty: false,
        error: null,
        validationErrors: undefined,
      })
    } catch (err) {
      set(toErrorState(err, 'Failed to publish module'))
      throw err
    }
  },

  closeDesigner: () => {
    set({ isOpen: false, moduleId: null, draft: null, isDirty: false, expectedVersion: 1, error: null, validationErrors: undefined })
  },

  addConfigField: (field) => {
    const { draft } = get()
    if (!draft) return

    const fields = schemaToConfigFields(draft.configSchema as Record<string, unknown> | undefined)
    fields.push(field)

    const newSchema = {
      type: 'object',
      properties: configFieldsToSchema(fields),
    }

    set({
      draft: { ...draft, configSchema: newSchema },
      isDirty: true,
    })
  },

  updateConfigField: (key, field) => {
    const { draft } = get()
    if (!draft) return

    const fields = schemaToConfigFields(draft.configSchema as Record<string, unknown> | undefined)
    const idx = fields.findIndex((f) => f.key === key)
    if (idx === -1) return

    // If key changed, remove old and add new
    if (key !== field.key) {
      fields.splice(idx, 1, field)
    } else {
      fields[idx] = field
    }

    const newSchema = {
      type: 'object',
      properties: configFieldsToSchema(fields),
    }

    set({
      draft: { ...draft, configSchema: newSchema },
      isDirty: true,
    })
  },

  removeConfigField: (key) => {
    const { draft } = get()
    if (!draft) return

    const fields = schemaToConfigFields(draft.configSchema as Record<string, unknown> | undefined)
    const newFields = fields.filter((f) => f.key !== key)

    const newSchema = {
      type: 'object',
      properties: configFieldsToSchema(newFields),
    }

    set({
      draft: { ...draft, configSchema: newSchema },
      isDirty: true,
    })
  },

  reorderConfigFields: (fromIndex, toIndex) => {
    const { draft } = get()
    if (!draft) return

    const fields = schemaToConfigFields(draft.configSchema as Record<string, unknown> | undefined)
    if (toIndex < 0 || toIndex >= fields.length) return

    const [moved] = fields.splice(fromIndex, 1)
    fields.splice(toIndex, 0, moved)

    const newSchema = {
      type: 'object',
      properties: configFieldsToSchema(fields),
    }

    set({
      draft: { ...draft, configSchema: newSchema },
      isDirty: true,
    })
  },

  addExtendedPort: (direction, port) => {
    const { draft } = get()
    if (!draft) return

    const key = directionKey(direction)
    const core = corePortIds(draft.baseKind)
    // Never shadow a core port; core ids belong to the baseKind contract.
    if (core[key].has(port.id)) return
    if (draft.ports[key].some((p) => p.id === port.id)) return

    set({
      draft: {
        ...draft,
        ports: { ...draft.ports, [key]: [...draft.ports[key], port] },
      },
      isDirty: true,
      error: null,
      validationErrors: undefined,
    })
  },

  updateExtendedPort: (direction, id, port) => {
    const { draft } = get()
    if (!draft) return

    const key = directionKey(direction)
    const core = corePortIds(draft.baseKind)
    const isCore = core[key].has(id)

    const ports = draft.ports[key].map((p) => {
      if (p.id !== id) return p
      if (isCore) {
        // Core contract is locked (id/type/cardinality); only label may change.
        return { ...p, label: port.label }
      }
      return { ...port, id }
    })

    set({
      draft: { ...draft, ports: { ...draft.ports, [key]: ports } },
      isDirty: true,
      error: null,
      validationErrors: undefined,
    })
  },

  deleteExtendedPort: (direction, id) => {
    const { draft } = get()
    if (!draft) return

    const key = directionKey(direction)
    const core = corePortIds(draft.baseKind)
    // Core ports cannot be removed.
    if (core[key].has(id)) return

    set({
      draft: {
        ...draft,
        ports: { ...draft.ports, [key]: draft.ports[key].filter((p) => p.id !== id) },
      },
      isDirty: true,
      error: null,
      validationErrors: undefined,
    })
  },

  setPortBinding: (direction, id, binding) => {
    const { draft } = get()
    if (!draft) return

    const key = directionKey(direction)
    const ports = draft.ports[key].map((p) =>
      p.id === id ? { ...p, binding: binding ? binding : undefined } : p,
    )

    set({
      draft: { ...draft, ports: { ...draft.ports, [key]: ports } },
      isDirty: true,
      error: null,
      validationErrors: undefined,
    })
  },
}))
