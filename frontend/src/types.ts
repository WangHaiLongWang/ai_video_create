import type { Edge, Node } from '@xyflow/react'

export type NodeKind =
  | 'textInput'
  | 'storyboard'
  | 'textToImage'
  | 'imageToVideo'
  | 'videoConcat'
  | 'output'

export type RunStatus = 'idle' | 'waiting' | 'running' | 'completed' | 'failed'

/* ==================== Field Definitions ==================== */

export type FieldType = 'text' | 'textarea' | 'number' | 'boolean' | 'select' | 'multi_select' | 'json' | 'prompt'

export interface FieldOption {
  label: string
  value: string
}

export interface FieldDefinition {
  id: string            // snake_case, unique within node
  label: string         // display name
  type: FieldType
  description?: string
  required?: boolean
  default?: string | number | boolean
  options?: FieldOption[]  // for select/multi_select
  advanced?: boolean    // hidden by default in simple mode
}

export interface PortInfo {
  id: string
  type: string
  required: boolean
  cardinality: 'one' | 'many'
  label?: string
}

export type StudioNodeData = {
  label: string
  description: string
  kind: NodeKind
  inputType?: string      // keep for backward compat
  outputType?: string     // keep for backward compat
  status: RunStatus
  config: Record<string, string | number | boolean>
  fieldSchema?: FieldDefinition[]
  ports?: {
    inputs: PortInfo[]
    outputs: PortInfo[]
  }
} & Record<string, unknown>

export interface CatalogNodeData {
  label: string
  description: string
  kind: NodeKind
  inputType?: string
  outputType?: string
  config: Record<string, string | number | boolean>
}

export type StudioNode = Node<StudioNodeData>

export type EdgeMode = 'direct' | 'map' | 'aggregate' | 'direct-by-key'

export interface EdgeData {
  mode?: EdgeMode
  sourcePath?: string
  targetPath?: string
  itemKey?: string
  order?: number
  label?: string
  [key: string]: unknown
}

export type EnhancedEdge = Edge<EdgeData>

export interface WorkflowSpec {
  schemaVersion: '1.0' | '2.0'
  manifestVersion?: string
  id: string
  name: string
  description?: string
  nodes: StudioNode[]
  edges: EnhancedEdge[]
  viewport?: { x: number; y: number; zoom: number }
  metadata?: Record<string, unknown>
}
