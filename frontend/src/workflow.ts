import type { Edge } from '@xyflow/react'
import type { CatalogNodeData, NodeKind, StudioNode, WorkflowSpec } from './types'

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
    config: { provider: 'Mock', duration: 4, motion: 'slow push', mapOver: true },
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
  const item = nodeCatalog[kind]
  return {
    id: id ?? `${kind}-${crypto.randomUUID()}`,
    type: 'studio',
    position: { x, y },
    data: { ...item, config: { ...item.config }, status: 'idle' },
  }
}

export function createPromptToVideoWorkflow(prompt?: string): WorkflowSpec {
  const nodes = order.map((kind, index) => createNode(kind, 110 + index * 285, index % 2 ? 220 : 150, `${kind}-1`))
  if (prompt) nodes[0].data.config.prompt = prompt
  const edges: Edge[] = nodes.slice(1).map((node, index) => ({
    id: `edge-${index + 1}`,
    source: nodes[index].id,
    target: node.id,
    type: 'smoothstep',
    animated: false,
  }))
  return { schemaVersion: '1.0', id: 'prompt-to-video', name: '提示词到短视频', nodes, edges }
}

export function validateConnection(source: StudioNode, target: StudioNode): boolean {
  return Boolean(source.data.outputType && target.data.inputType && source.data.outputType === target.data.inputType)
}
