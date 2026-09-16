import type { WorkflowSpec } from '../../src/types'

/**
 * Default workflow matching createPromptToVideoWorkflow().
 * Used as the baseline for most E2E tests.
 */
export const defaultWorkflow: WorkflowSpec = {
  schemaVersion: '1.0',
  id: 'prompt-to-video',
  name: '提示词到短视频',
  nodes: [
    {
      id: 'textInput-1',
      type: 'studio',
      position: { x: 110, y: 150 },
      data: {
        label: '主题输入',
        description: '输入创作主题与要求',
        kind: 'textInput',
        outputType: 'text',
        status: 'idle',
        config: { prompt: '雨夜，一名送信人在未来城市穿行' },
      },
    },
    {
      id: 'storyboard-1',
      type: 'studio',
      position: { x: 395, y: 220 },
      data: {
        label: '分镜生成',
        description: '将主题转换为结构化分镜',
        kind: 'storyboard',
        inputType: 'text',
        outputType: 'list<scene>',
        status: 'idle',
        config: { provider: 'Mock', scenes: 5, style: 'cinematic noir' },
      },
    },
    {
      id: 'textToImage-1',
      type: 'studio',
      position: { x: 680, y: 150 },
      data: {
        label: '文生图',
        description: '逐镜生成关键帧',
        kind: 'textToImage',
        inputType: 'list<scene>',
        outputType: 'list<image>',
        status: 'idle',
        config: { ratio: '16:9', mapOver: true },
      },
    },
    {
      id: 'imageToVideo-1',
      type: 'studio',
      position: { x: 965, y: 220 },
      data: {
        label: '图生视频',
        description: '逐张图片生成视频片段',
        kind: 'imageToVideo',
        inputType: 'list<image>',
        outputType: 'list<video>',
        status: 'idle',
        config: { resolution: '480P', ratio: 'adaptive', duration: 5, audio: true, prompt_extend: true, watermark: false, mapOver: true },
      },
    },
    {
      id: 'videoConcat-1',
      type: 'studio',
      position: { x: 1250, y: 150 },
      data: {
        label: '视频合成',
        description: '按分镜顺序合并片段',
        kind: 'videoConcat',
        inputType: 'list<video>',
        outputType: 'video',
        status: 'idle',
        config: { transition: 'crossfade', format: 'mp4' },
      },
    },
    {
      id: 'output-1',
      type: 'studio',
      position: { x: 1535, y: 220 },
      data: {
        label: '成片输出',
        description: '预览与下载最终结果',
        kind: 'output',
        inputType: 'video',
        status: 'idle',
        config: { filename: 'future-rain.mp4' },
      },
    },
  ],
  edges: [
    { id: 'edge-1', source: 'textInput-1', target: 'storyboard-1', type: 'smoothstep', animated: false },
    { id: 'edge-2', source: 'storyboard-1', target: 'textToImage-1', type: 'smoothstep', animated: false },
    { id: 'edge-3', source: 'textToImage-1', target: 'imageToVideo-1', type: 'smoothstep', animated: false },
    { id: 'edge-4', source: 'imageToVideo-1', target: 'videoConcat-1', type: 'smoothstep', animated: false },
    { id: 'edge-5', source: 'videoConcat-1', target: 'output-1', type: 'smoothstep', animated: false },
  ],
}

/**
 * Minimal workflow with only two nodes for quick tests.
 */
export const minimalWorkflow: WorkflowSpec = {
  schemaVersion: '1.0',
  id: 'minimal',
  name: '最小工作流',
  nodes: [
    {
      id: 'textInput-1',
      type: 'studio',
      position: { x: 110, y: 150 },
      data: {
        label: '主题输入',
        description: '输入创作主题与要求',
        kind: 'textInput',
        outputType: 'text',
        status: 'idle',
        config: { prompt: '测试提示词' },
      },
    },
    {
      id: 'output-1',
      type: 'studio',
      position: { x: 500, y: 150 },
      data: {
        label: '成片输出',
        description: '预览与下载最终结果',
        kind: 'output',
        inputType: 'video',
        status: 'idle',
        config: { filename: 'output.mp4' },
      },
    },
  ],
  edges: [],
}

/**
 * Node kind metadata used for palette and assertion tests.
 */
export const nodeKinds = [
  { kind: 'textInput', label: '主题输入', outputType: 'text' },
  { kind: 'storyboard', label: '分镜生成', outputType: 'list<scene>' },
  { kind: 'textToImage', label: '文生图', outputType: 'list<image>' },
  { kind: 'imageToVideo', label: '图生视频', outputType: 'list<video>' },
  { kind: 'videoConcat', label: '视频合成', outputType: 'video' },
  { kind: 'output', label: '成片输出', outputType: undefined },
] as const
