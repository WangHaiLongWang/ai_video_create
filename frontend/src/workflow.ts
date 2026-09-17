import type { CatalogNodeData, NodeKind, StudioNode, WorkflowSpec } from './types'
import type { WorkflowSpecV2 } from './schemas/workflow-spec'
import { NODE_CATALOG } from './schemas/node-manifest'

export const nodeCatalog: Record<NodeKind, CatalogNodeData> = {
  textInput: {
    label: '主题输入',
    description: '输入创作主题与要求',
    kind: 'textInput',
    outputType: 'text',
    config: { prompt: '雨夜，一名送信人在未来城市穿行' },
  },
  storyboard: {
    label: '分镜生成',
    description: '将主题转换为结构化分镜',
    kind: 'storyboard',
    inputType: 'text',
    outputType: 'list<scene>',
    config: { provider: 'Mock', scenes: 5, style: 'cinematic noir' },
  },
  textToImage: {
    label: '文生图',
    description: '逐镜生成关键帧',
    kind: 'textToImage',
    inputType: 'list<scene>',
    outputType: 'list<image>',
    config: { ratio: '16:9', mapOver: true },
  },
  imageToVideo: {
    label: '图生视频',
    description: '逐张图片生成视频片段',
    kind: 'imageToVideo',
    inputType: 'list<image>',
    outputType: 'list<video>',
    config: { resolution: '480P', ratio: 'adaptive', duration: 5, audio: true, prompt_extend: true, watermark: false, mapOver: true },
  },
  videoConcat: {
    label: '视频合成',
    description: '按分镜顺序合并片段',
    kind: 'videoConcat',
    inputType: 'list<video>',
    outputType: 'video',
    config: { transition: 'crossfade', format: 'mp4' },
  },
  output: {
    label: '成片输出',
    description: '预览与下载最终结果',
    kind: 'output',
    inputType: 'video',
    config: { filename: 'future-rain.mp4' },
  },
}

const order: NodeKind[] = [
  'textInput',
  'storyboard',
  'textToImage',
  'imageToVideo',
  'videoConcat',
  'output',
]

export function createNode(kind: NodeKind, x: number, y: number, id?: string): StudioNode {
  const manifest = NODE_CATALOG[kind]
  const item = nodeCatalog[kind]
  const ports = manifest ? {
    inputs: manifest.ports.inputs.map(p => ({ id: p.id, type: p.type, required: p.required, cardinality: p.cardinality, label: p.label ?? p.id })),
    outputs: manifest.ports.outputs.map(p => ({ id: p.id, type: p.type, required: false, cardinality: p.cardinality, label: p.label ?? p.id })),
  } : undefined

  return {
    id: id ?? `${kind}-${crypto.randomUUID()}`,
    type: 'studio',
    position: { x, y },
    data: {
      ...item,
      config: { ...item.config },
      inputType: manifest?.ports.inputs[0]?.type,
      outputType: manifest?.ports.outputs[0]?.type,
      status: 'idle',
      ports,
    },
  }
}

export function createPromptToVideoWorkflow(prompt?: string): WorkflowSpecV2 {
  const NODE_WIDTH = 228
  const GAP = 60
  const nodes = order.map((kind, index) => createNode(kind, 110 + index * (NODE_WIDTH + GAP), index % 2 ? 220 : 150, `${kind}-1`))
  if (prompt) nodes[0].data.config.prompt = prompt

  // Create edges with sourceHandle/targetHandle from node manifests
  const edges = []
  for (let i = 0; i < order.length - 1; i++) {
    const sourceKind = order[i]
    const targetKind = order[i + 1]
    const sourceManifest = NODE_CATALOG[sourceKind]
    const targetManifest = NODE_CATALOG[targetKind]
    edges.push({
      id: `edge-${i + 1}`,
      source: nodes[i].id,
      sourceHandle: sourceManifest?.ports.outputs[0]?.id ?? 'out',
      target: nodes[i + 1].id,
      targetHandle: targetManifest?.ports.inputs[0]?.id ?? 'in',
      // type omitted → React Flow uses 'default' → our custom LabelEdge (smoothstep path)
      data: { mode: 'direct' as const, label: '' },
    })
  }

  return {
    schemaVersion: '2.0',
    manifestVersion: '1.0',
    id: 'prompt-to-video',
    name: prompt ? `视频生成: ${prompt.slice(0, 30)}` : 'Prompt → 视频工作流',
    nodes,
    edges,
    viewport: { x: 0, y: 0, zoom: 1 },
    metadata: { tags: ['default'] },
  }
}

/** Legacy validateConnection — kept for backward compat with tests */
export function validateConnection(source: StudioNode, target: StudioNode): boolean {
  return Boolean(source.data.outputType && target.data.inputType && source.data.outputType === target.data.inputType)
}
