import type { PortType } from './node-manifest'
import { NODE_CATALOG } from './node-manifest'

// ---------------------------------------------------------------------------
// Module category
// ---------------------------------------------------------------------------
export type ModuleCategory = 'Input' | 'LLM' | 'Image' | 'Video' | 'Transform' | 'Output'

// ---------------------------------------------------------------------------
// Module icon
// ---------------------------------------------------------------------------
export type ModuleIcon =
  | 'image-square'
  | 'video'
  | 'type'
  | 'code'
  | 'chat-circle'
  | 'lightning'
  | 'arrow-right'
  | 'arrows-left-right'
  | 'export'
  | 'import'
  | 'film-strip'
  | 'music-note'
  | 'microphone'
  | 'paint-brush'
  | 'wand'
  | 'sparkle'

// ---------------------------------------------------------------------------
// Module status
// ---------------------------------------------------------------------------
export type ModuleStatus = 'draft' | 'published' | 'archived'

// ---------------------------------------------------------------------------
// Provider policy — controls which providers are allowed for a module
// ---------------------------------------------------------------------------
export interface ProviderPolicy {
  capability: string       // "text" | "image" | "video"
  allowed: string[]        // provider names
  default?: string
  locked: boolean
}

// ---------------------------------------------------------------------------
// Module port — mirrors PortDefinition but scoped to module contracts
// ---------------------------------------------------------------------------
export interface ModulePort {
  id: string
  type: PortType           // reuses PortType from node-manifest
  required: boolean
  cardinality: 'one' | 'many'
  label?: string
  /**
   * Whitelist binding for extended ports. Canonical form is a bare config
   * field key (e.g. "ref_image_url") naming a property in `configSchema`,
   * i.e. the port maps to `config.<binding>`. Core ports (ids defined by the
   * baseKind manifest) never need a binding; an extended port without one
   * cannot be published or executed (UNBOUND_MODULE_PORT).
   */
  binding?: string
}

// ---------------------------------------------------------------------------
// Structured validation error — mirrors backend PortError
// ---------------------------------------------------------------------------
export interface PortError {
  field: string    // e.g. "ports.inputs[1].binding"
  error: string    // e.g. "UNBOUND_MODULE_PORT"
  message: string
}

// ---------------------------------------------------------------------------
// Module definition — the core contract for reusable node templates
// ---------------------------------------------------------------------------
export interface ModuleDefinition {
  id: string               // e.g. "builtin.seedream.text-to-image"
  version: string          // semver
  status: ModuleStatus
  /** Optimistic-lock token returned by the module API. */
  expectedVersion?: number
  baseKind: string         // matches existing NodeKind
  category: string
  label: string
  description?: string
  icon?: string
  providerPolicy: ProviderPolicy
  configSchema?: Record<string, unknown>   // JSON Schema
  defaultConfig?: Record<string, unknown>
  ports: {
    inputs: ModulePort[]
    outputs: ModulePort[]
  }
  execution?: {
    mapOver?: string
    aggregate?: string
  }
  metadata?: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Publish blockers — client-side mirror of the UNBOUND_MODULE_PORT gate
// ---------------------------------------------------------------------------
/**
 * Collect the blockers that stop a module from being published/executed.
 * Mirrors the backend rule: an extended port (any port id not present in the
 * baseKind's NODE_CATALOG manifest) must carry a non-empty `binding`.
 */
export function collectPublishBlockers(
  ports: { inputs: ModulePort[]; outputs: ModulePort[] },
  baseKind: string,
): PortError[] {
  const manifest = NODE_CATALOG[baseKind as keyof typeof NODE_CATALOG]
  const coreIds = {
    inputs: new Set((manifest?.ports.inputs ?? []).map((p) => p.id)),
    outputs: new Set((manifest?.ports.outputs ?? []).map((p) => p.id)),
  }
  const blockers: PortError[] = []
  for (const direction of ['inputs', 'outputs'] as const) {
    ports[direction].forEach((port, i) => {
      if (!coreIds[direction].has(port.id) && !port.binding) {
        blockers.push({
          field: `ports.${direction}[${i}].binding`,
          error: 'UNBOUND_MODULE_PORT',
          message: (
            `Extension ${direction === 'inputs' ? 'input' : 'output'} port '${port.id}' ` +
            `has no binding to config field`
          ),
        })
      }
    })
  }
  return blockers
}

// ---------------------------------------------------------------------------
// Node instance extension — metadata carried on a canvas node referencing a module
// ---------------------------------------------------------------------------
export interface NodeInstanceExtension {
  moduleId?: string
  moduleVersion?: string
  configOverrides?: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Config schema field — used in Module Designer for defining module config
// ---------------------------------------------------------------------------
export type ConfigFieldType = 'string' | 'integer' | 'number' | 'boolean' | 'enum'

export interface ConfigSchemaField {
  key: string
  type: ConfigFieldType
  title: string
  default?: string | number | boolean
  required: boolean
  // For enum type
  enumOptions?: string[]
  // For string type
  format?: 'text' | 'textarea'
  // For number types
  minimum?: number
  maximum?: number
}

// ---------------------------------------------------------------------------
// Module Designer state
// ---------------------------------------------------------------------------
export interface ModuleDesignerState {
  isOpen: boolean
  moduleId: string | null  // null = creating new
  draft: ModuleDefinition | null
  isDirty: boolean
  expectedVersion: number
  error: string | null
  /** Structured validation errors from the module API (e.g. UNBOUND_MODULE_PORT). */
  validationErrors?: PortError[]
}

// ---------------------------------------------------------------------------
// Built-in modules — Seedream as the first entry
// ---------------------------------------------------------------------------
export const BUILTIN_MODULES: ModuleDefinition[] = [
  {
    id: 'builtin.seedream.text-to-image',
    version: '1.0.0',
    status: 'published',
    baseKind: 'textToImage',
    category: 'Image',
    label: 'Seedream 文生图',
    description: '使用火山方舟 Seedream 生成图片',
    icon: 'image-square',
    providerPolicy: {
      capability: 'image',
      allowed: ['doubao'],
      default: 'doubao',
      locked: true,
    },
    configSchema: {
      type: 'object',
      properties: {
        image_model: { type: 'string', title: '模型 / Endpoint ID' },
        size: { type: 'string', title: '图片尺寸', default: '1280x720' },
        negative_prompt: { type: 'string', format: 'textarea' },
        seed: { type: 'integer', minimum: -1, default: -1 },
        watermark: { type: 'boolean', default: false },
        variantCount: { type: 'integer', minimum: 1, maximum: 4, default: 1 },
      },
      required: ['image_model'],
    },
    defaultConfig: {
      provider: 'doubao',
      image_model: 'doubao-seedream-5-0-pro-260628',
      size: '1280x720',
      mapOver: true,
    },
    ports: {
      inputs: [
        { id: 'scene', type: 'scene', required: true, cardinality: 'one' },
      ],
      outputs: [
        { id: 'image', type: 'image', required: false, cardinality: 'one' },
      ],
    },
    execution: { mapOver: 'scene' },
    metadata: { builtin: true, provider: 'volcengine' },
  },
]
