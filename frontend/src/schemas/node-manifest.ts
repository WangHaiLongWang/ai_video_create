import type { NodeKind } from '../types'

// ---------------------------------------------------------------------------
// Port types
// ---------------------------------------------------------------------------
export type PortType = 'text' | 'scene' | 'image' | 'video' | 'audio' | 'asset' | 'any'
export type Cardinality = 'one' | 'many'

export interface PortDefinition {
  id: string           // stable handle ID, e.g. "image", "scenes", "scene"
  type: PortType       // base type
  required: boolean    // only meaningful for inputs
  cardinality: Cardinality
  label?: string       // human-readable, defaults to id
}

export interface NodeManifest {
  kind: string             // matches NodeKind
  version: string          // semver
  category: string         // "input" | "transform" | "video" | "output"
  label: string            // display name
  description?: string
  ports: {
    inputs: PortDefinition[]
    outputs: PortDefinition[]
  }
  configSchema?: Record<string, unknown>  // JSON Schema for node config
  execution?: {
    mapOver?: string       // port ID to map over (e.g. "image" for per-scene expansion)
    aggregate?: string     // port ID to aggregate into
  }
}

// ---------------------------------------------------------------------------
// Catalog — one entry per NodeKind
// ---------------------------------------------------------------------------
export const NODE_CATALOG: Record<NodeKind, NodeManifest> = {
  textInput: {
    kind: 'textInput',
    version: '1.0.0',
    category: 'input',
    label: '主题输入',
    description: '输入创作主题与要求',
    ports: {
      inputs: [],
      outputs: [
        { id: 'text', type: 'text', required: false, cardinality: 'one' },
      ],
    },
  },

  storyboard: {
    kind: 'storyboard',
    version: '1.0.0',
    category: 'transform',
    label: '分镜生成',
    description: '将主题转换为结构化分镜',
    ports: {
      inputs: [
        { id: 'prompt', type: 'text', required: true, cardinality: 'one' },
      ],
      outputs: [
        { id: 'scenes', type: 'scene', required: false, cardinality: 'many' },
      ],
    },
  },

  textToImage: {
    kind: 'textToImage',
    version: '1.0.0',
    category: 'transform',
    label: '文生图',
    description: '逐镜生成关键帧',
    ports: {
      inputs: [
        { id: 'scene', type: 'scene', required: true, cardinality: 'one' },
      ],
      outputs: [
        { id: 'image', type: 'image', required: false, cardinality: 'one' },
      ],
    },
    execution: { mapOver: 'scene' },
  },

  imageToVideo: {
    kind: 'imageToVideo',
    version: '1.0.0',
    category: 'video',
    label: '图生视频',
    description: '逐张图片生成视频片段',
    ports: {
      inputs: [
        { id: 'image', type: 'image', required: true, cardinality: 'one' },
        { id: 'scene', type: 'scene', required: false, cardinality: 'one' },
      ],
      outputs: [
        { id: 'video', type: 'video', required: false, cardinality: 'one' },
      ],
    },
    execution: { mapOver: 'image' },
  },

  videoConcat: {
    kind: 'videoConcat',
    version: '1.0.0',
    category: 'video',
    label: '视频合成',
    description: '按分镜顺序合并片段',
    ports: {
      inputs: [
        { id: 'video', type: 'video', required: true, cardinality: 'many' },
      ],
      outputs: [
        { id: 'video', type: 'video', required: false, cardinality: 'one' },
      ],
    },
  },

  output: {
    kind: 'output',
    version: '1.0.0',
    category: 'output',
    label: '成片输出',
    description: '预览与下载最终结果',
    ports: {
      inputs: [
        { id: 'video', type: 'video', required: true, cardinality: 'one' },
      ],
      outputs: [],
    },
  },
}
