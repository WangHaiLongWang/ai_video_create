import { addEdge, applyEdgeChanges, applyNodeChanges, type Connection, type EdgeChange, type NodeChange } from '@xyflow/react'
import { create } from 'zustand'
import * as api from './api'
import { createPromptToVideoWorkflow, validateConnection } from './workflow'
import type { StudioNode, WorkflowSpec } from './types'

const STORAGE_KEY = 'ai-video-create.workflow.v1'
const MAX_HISTORY = 30
const SAVE_DEBOUNCE_MS = 1000

function initialWorkflow(): WorkflowSpec {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) return JSON.parse(saved) as WorkflowSpec
  } catch {
    localStorage.removeItem(STORAGE_KEY)
  }
  return createPromptToVideoWorkflow()
}

function persistLocal(workflow: WorkflowSpec) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(workflow))
}

interface StudioState {
  workflow: WorkflowSpec
  selectedNodeId: string | null
  isRunning: boolean
  runMessage: string
  serverVersion: number | null
  isDirty: boolean

  // History
  past: WorkflowSpec[]
  future: WorkflowSpec[]

  // Actions
  setWorkflow: (workflow: WorkflowSpec) => void
  onNodesChange: (changes: NodeChange<StudioNode>[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onConnect: (connection: Connection) => void
  selectNode: (id: string | null) => void
  updateConfig: (key: string, value: string | number | boolean) => void
  runMock: () => Promise<void>
  stopRun: () => void
  undo: () => void
  redo: () => void
  canUndo: () => boolean
  canRedo: () => boolean
  saveToServer: () => Promise<void>
  loadFromServer: (id?: string) => Promise<void>
  serverSync: () => void
}

let runGeneration = 0
let saveTimer: ReturnType<typeof setTimeout> | null = null

function pushHistory(state: StudioState, workflow: WorkflowSpec): Pick<StudioState, 'past' | 'future'> {
  const past = [...state.past, state.workflow].slice(-MAX_HISTORY)
  return { past, future: [] }
}

function scheduleSave(get: () => StudioState) {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    get().saveToServer()
  }, SAVE_DEBOUNCE_MS)
}

export const useStudioStore = create<StudioState>((set, get) => ({
  workflow: initialWorkflow(),
  selectedNodeId: null,
  isRunning: false,
  runMessage: '准备执行',
  serverVersion: null,
  isDirty: false,
  past: [],
  future: [],

  setWorkflow: (workflow) => {
    const history = pushHistory(get(), workflow)
    persistLocal(workflow)
    set({ workflow, selectedNodeId: null, isDirty: true, ...history })
    scheduleSave(get)
  },

  onNodesChange: (changes) => set((state) => {
    const workflow = { ...state.workflow, nodes: applyNodeChanges(changes, state.workflow.nodes) }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  onEdgesChange: (changes) => set((state) => {
    const workflow = { ...state.workflow, edges: applyEdgeChanges(changes, state.workflow.edges) }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  onConnect: (connection) => set((state) => {
    const source = state.workflow.nodes.find((node) => node.id === connection.source)
    const target = state.workflow.nodes.find((node) => node.id === connection.target)
    if (!source || !target || !validateConnection(source, target)) return state
    const workflow = { ...state.workflow, edges: addEdge({ ...connection, type: 'smoothstep' }, state.workflow.edges) }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  selectNode: (selectedNodeId) => set({ selectedNodeId }),

  updateConfig: (key, value) => set((state) => {
    const nodes = state.workflow.nodes.map((node) => node.id === state.selectedNodeId
      ? { ...node, data: { ...node.data, config: { ...node.data.config, [key]: value } } }
      : node)
    const workflow = { ...state.workflow, nodes }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
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

  undo: () => set((state) => {
    if (state.past.length === 0) return state
    const previous = state.past[state.past.length - 1]
    const past = state.past.slice(0, -1)
    persistLocal(previous)
    return { workflow: previous, past, future: [state.workflow, ...state.future], selectedNodeId: null }
  }),

  redo: () => set((state) => {
    if (state.future.length === 0) return state
    const next = state.future[0]
    const future = state.future.slice(1)
    persistLocal(next)
    return { workflow: next, past: [...state.past, state.workflow], future, selectedNodeId: null }
  }),

  canUndo: () => get().past.length > 0,
  canRedo: () => get().future.length > 0,

  saveToServer: async () => {
    const { workflow, serverVersion, isDirty } = get()
    if (!isDirty) return
    try {
      if (serverVersion === null) {
        const result = await api.createWorkflow(workflow as unknown as Record<string, unknown>)
        set({ serverVersion: result.version, isDirty: false })
      } else {
        const result = await api.updateWorkflow(
          workflow.id,
          workflow as unknown as Record<string, unknown>,
          serverVersion,
        )
        set({ serverVersion: result.version, isDirty: false })
      }
    } catch (err) {
      console.warn('保存到服务器失败，保留本地数据:', err)
    }
  },

  loadFromServer: async (id?: string) => {
    try {
      if (id) {
        const detail = await api.getWorkflow(id)
        const spec = detail.spec as unknown as WorkflowSpec
        persistLocal(spec)
        set({ workflow: spec, serverVersion: detail.version, isDirty: false, past: [], future: [] })
      } else {
        const list = await api.fetchWorkflows()
        if (list.length > 0) {
          const latest = list[0]
          const detail = await api.getWorkflow(latest.id)
          const spec = detail.spec as unknown as WorkflowSpec
          persistLocal(spec)
          set({ workflow: spec, serverVersion: detail.version, isDirty: false, past: [], future: [] })
        }
      }
    } catch (err) {
      console.warn('从服务器加载失败，使用本地数据:', err)
    }
  },

  serverSync: () => {
    scheduleSave(get)
  },
}))
