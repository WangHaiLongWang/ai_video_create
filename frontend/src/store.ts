import { addEdge, applyEdgeChanges, applyNodeChanges, type Connection, type EdgeChange, type NodeChange } from '@xyflow/react'
import { create } from 'zustand'
import * as api from './api'
import { createPromptToVideoWorkflow, validateConnection } from './workflow'
import type { RunStatus, StudioNode, WorkflowSpec } from './types'

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

interface ExecutionState {
  executionId: string | null
  status: string
  taskCount: number
  completedCount: number
  tasks: Map<string, api.TaskResponse>
  events: api.ExecutionEvent[]
}

interface StudioState {
  workflow: WorkflowSpec
  selectedNodeId: string | null
  isRunning: boolean
  runMessage: string
  serverVersion: number | null
  isDirty: boolean
  execution: ExecutionState | null

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
  runExecution: () => Promise<void>
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
let pollTimer: ReturnType<typeof setTimeout> | null = null

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
  execution: null,
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

  runExecution: async () => {
    const generation = ++runGeneration
    const { workflow, serverVersion } = get()

    // 先保存到服务器
    set((state) => ({
      isRunning: true,
      runMessage: '正在保存工作流...',
      workflow: { ...state.workflow, nodes: state.workflow.nodes.map((node) => ({ ...node, data: { ...node.data, status: 'waiting' } })) },
    }))

    try {
      // 如果未保存到服务器，先创建
      if (serverVersion === null) {
        const result = await api.createWorkflow(workflow as unknown as Record<string, unknown>)
        set({ serverVersion: result.version, isDirty: false })
      } else if (get().isDirty) {
        const result = await api.updateWorkflow(
          workflow.id,
          workflow as unknown as Record<string, unknown>,
          serverVersion,
        )
        set({ serverVersion: result.version, isDirty: false })
      }

      if (generation !== runGeneration) return

      // 启动执行
      set({ runMessage: '正在启动执行...' })
      const execResult = await api.startExecution(workflow.id)

      if (generation !== runGeneration) return

      // 初始化执行状态
      const executionState: ExecutionState = {
        executionId: execResult.id,
        status: execResult.status,
        taskCount: execResult.task_count,
        completedCount: 0,
        tasks: new Map(),
        events: [],
      }
      set({ execution: executionState, runMessage: `执行已启动，${execResult.task_count} 个任务` })

      // 轮询执行状态
      const pollLoop = async () => {
        const currentExec = get().execution
        if (!currentExec?.executionId || generation !== runGeneration) return

        try {
          const tasks = await api.getExecutionTasks(currentExec.executionId)
          if (generation !== runGeneration) return

          const taskMap = new Map<string, api.TaskResponse>()
          let completedCount = 0

          for (const task of tasks) {
            taskMap.set(task.id, task)
            if (task.status === 'completed') completedCount++
          }

          // 更新节点状态
          const updatedNodes = get().workflow.nodes.map((node) => {
            const nodeTasks = tasks.filter((t) => t.node_id === node.id)
            if (nodeTasks.length === 0) return node

            const allCompleted = nodeTasks.every((t) => t.status === 'completed')
            const anyFailed = nodeTasks.some((t) => t.status === 'failed')
            const anyRunning = nodeTasks.some((t) => t.status === 'running')

            let status: RunStatus = node.data.status
            if (allCompleted) status = 'completed'
            else if (anyFailed) status = 'failed'
            else if (anyRunning) status = 'running'

            return { ...node, data: { ...node.data, status } }
          })

          set((state) => ({
            workflow: { ...state.workflow, nodes: updatedNodes },
            execution: state.execution ? {
              ...state.execution,
              tasks: taskMap,
              completedCount,
            } : null,
            runMessage: `执行中: ${completedCount}/${tasks.length} 任务完成`,
          }))

          // 检查是否完成
          const execStatus = await api.getExecution(currentExec.executionId)
          if (generation !== runGeneration) return

          if (execStatus.status === 'completed' || execStatus.status === 'failed') {
            set({
              isRunning: false,
              runMessage: execStatus.status === 'completed' ? '执行完成' : '执行失败',
              execution: get().execution ? { ...get().execution!, status: execStatus.status } : null,
            })
            return
          }

          // 继续轮询
          if (generation === runGeneration) {
            pollTimer = setTimeout(pollLoop, 1000)
          }

        } catch (err) {
          console.error('轮询执行状态失败:', err)
          if (generation === runGeneration) {
            pollTimer = setTimeout(pollLoop, 2000)
          }
        }
      }

      // 开始轮询
      pollLoop()

    } catch (err) {
      console.error('执行失败:', err)
      set({
        isRunning: false,
        runMessage: `执行失败: ${err instanceof Error ? err.message : '未知错误'}`,
        execution: null,
      })
    }
  },

  stopRun: async () => {
    runGeneration += 1
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }

    // 取消后端执行
    const { execution } = get()
    if (execution?.executionId) {
      try {
        await api.cancelExecution(execution.executionId)
      } catch (err) {
        console.warn('取消执行失败:', err)
      }
    }

    set((state) => ({
      isRunning: false,
      runMessage: '执行已取消',
      execution: state.execution ? { ...state.execution, status: 'cancelled' } : null,
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
