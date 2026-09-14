import { addEdge, applyEdgeChanges, applyNodeChanges, type Connection, type EdgeChange, type NodeChange } from '@xyflow/react'
import { create } from 'zustand'
import { createPromptToVideoWorkflow, validateConnection } from './workflow'
import type { StudioNode, WorkflowSpec } from './types'

const STORAGE_KEY = 'ai-video-create.workflow.v1'

function initialWorkflow(): WorkflowSpec {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) return JSON.parse(saved) as WorkflowSpec
  } catch {
    localStorage.removeItem(STORAGE_KEY)
  }
  return createPromptToVideoWorkflow()
}

interface StudioState {
  workflow: WorkflowSpec
  selectedNodeId: string | null
  isRunning: boolean
  runMessage: string
  setWorkflow: (workflow: WorkflowSpec) => void
  onNodesChange: (changes: NodeChange<StudioNode>[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onConnect: (connection: Connection) => void
  selectNode: (id: string | null) => void
  updateConfig: (key: string, value: string | number | boolean) => void
  runMock: () => Promise<void>
  stopRun: () => void
}

let runGeneration = 0

export const useStudioStore = create<StudioState>((set, get) => ({
  workflow: initialWorkflow(),
  selectedNodeId: null,
  isRunning: false,
  runMessage: '准备执行',
  setWorkflow: (workflow) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(workflow))
    set({ workflow, selectedNodeId: null })
  },
  onNodesChange: (changes) => set((state) => {
    const workflow = { ...state.workflow, nodes: applyNodeChanges(changes, state.workflow.nodes) }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(workflow))
    return { workflow }
  }),
  onEdgesChange: (changes) => set((state) => {
    const workflow = { ...state.workflow, edges: applyEdgeChanges(changes, state.workflow.edges) }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(workflow))
    return { workflow }
  }),
  onConnect: (connection) => set((state) => {
    const source = state.workflow.nodes.find((node) => node.id === connection.source)
    const target = state.workflow.nodes.find((node) => node.id === connection.target)
    if (!source || !target || !validateConnection(source, target)) return state
    const workflow = { ...state.workflow, edges: addEdge({ ...connection, type: 'smoothstep' }, state.workflow.edges) }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(workflow))
    return { workflow }
  }),
  selectNode: (selectedNodeId) => set({ selectedNodeId }),
  updateConfig: (key, value) => set((state) => {
    const nodes = state.workflow.nodes.map((node) => node.id === state.selectedNodeId
      ? { ...node, data: { ...node.data, config: { ...node.data.config, [key]: value } } }
      : node)
    const workflow = { ...state.workflow, nodes }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(workflow))
    return { workflow }
  }),
  runMock: async () => {
    const generation = ++runGeneration
    set((state) => ({
      isRunning: true,
      runMessage: '正在编译工作流',
      workflow: { ...state.workflow, nodes: state.workflow.nodes.map((node) => ({ ...node, data: { ...node.data, status: 'waiting' } })) },
    }))
    for (const node of get().workflow.nodes) {
      if (generation !== runGeneration) return
      set((state) => ({
        runMessage: `正在执行：${node.data.label}`,
        workflow: { ...state.workflow, nodes: state.workflow.nodes.map((item) => item.id === node.id ? { ...item, data: { ...item.data, status: 'running' } } : item) },
      }))
      await new Promise((resolve) => setTimeout(resolve, node.data.kind === 'imageToVideo' ? 1100 : 650))
      if (generation !== runGeneration) return
      set((state) => ({
        workflow: { ...state.workflow, nodes: state.workflow.nodes.map((item) => item.id === node.id ? { ...item, data: { ...item.data, status: 'completed' } } : item) },
      }))
    }
    set({ isRunning: false, runMessage: '执行完成，6 个节点均已生成结果' })
  },
  stopRun: () => {
    runGeneration += 1
    set((state) => ({
      isRunning: false,
      runMessage: '执行已取消',
      workflow: { ...state.workflow, nodes: state.workflow.nodes.map((node) => node.data.status === 'running' || node.data.status === 'waiting' ? { ...node, data: { ...node.data, status: 'idle' } } : node) },
    }))
  },
}))

