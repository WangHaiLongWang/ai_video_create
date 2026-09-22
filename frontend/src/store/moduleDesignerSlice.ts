import { create } from 'zustand'
import type { ModuleDefinition, ModuleDesignerState, ConfigSchemaField } from '../schemas/module-definition'

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
    ports: {
      inputs: [],
      outputs: [],
    },
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
}

type ModuleDesignerStore = ModuleDesignerState & ModuleDesignerActions

// ---------------------------------------------------------------------------
// API helpers (lazy imports to avoid circular deps)
// ---------------------------------------------------------------------------
async function apiSaveModule(draft: ModuleDefinition): Promise<void> {
  const method = draft.id ? 'PUT' : 'POST'
  const url = draft.id ? `/api/modules/${draft.id}` : '/api/modules'
  await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(draft),
  })
}

async function apiPublishModule(moduleId: string): Promise<void> {
  await fetch(`/api/modules/${moduleId}/publish`, { method: 'POST' })
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------
export const useModuleDesignerStore = create<ModuleDesignerStore>((set, get) => ({
  isOpen: false,
  moduleId: null,
  draft: null,
  isDirty: false,

  openDesigner: (moduleId?: string, module?: ModuleDefinition) => {
    if (module) {
      set({ isOpen: true, moduleId: module.id, draft: { ...module }, isDirty: false })
    } else {
      const draft = createEmptyDraft()
      if (moduleId) {
        draft.id = moduleId
      }
      set({ isOpen: true, moduleId: null, draft, isDirty: false })
    }
  },

  updateDraft: (partial) => {
    const { draft } = get()
    if (!draft) return
    const newDraft = { ...draft, ...partial }

    // Auto-update ID from label if creating new
    if (partial.label !== undefined && get().moduleId === null) {
      newDraft.id = generateModuleId(partial.label, newDraft.category)
    }

    set({ draft: newDraft, isDirty: true })
  },

  saveDraft: async () => {
    const { draft } = get()
    if (!draft) return
    try {
      await apiSaveModule(draft)
      set({ isDirty: false })
    } catch (err) {
      console.error('Failed to save module:', err)
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
      await apiPublishModule(draft.id)
      set({ draft: draft ? { ...draft, status: 'published' } : null, isDirty: false })
    } catch (err) {
      console.error('Failed to publish module:', err)
      throw err
    }
  },

  closeDesigner: () => {
    set({ isOpen: false, moduleId: null, draft: null, isDirty: false })
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
}))
