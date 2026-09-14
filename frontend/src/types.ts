import type { Edge, Node } from '@xyflow/react'

export type NodeKind =
  | 'textInput'
  | 'storyboard'
  | 'textToImage'
  | 'imageToVideo'
  | 'videoConcat'
  | 'output'

export type RunStatus = 'idle' | 'waiting' | 'running' | 'completed' | 'failed'

export type StudioNodeData = {
  label: string
  description: string
  kind: NodeKind
  inputType?: string
  outputType?: string
  status: RunStatus
  config: Record<string, string | number | boolean>
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

export interface WorkflowSpec {
  schemaVersion: '1.0'
  id: string
  name: string
  nodes: StudioNode[]
  edges: Edge[]
}
