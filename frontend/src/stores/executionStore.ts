/**
 * executionStore — 独立的执行状态管理
 *
 * 从原 store.ts 中拆分出执行相关逻辑，包括:
 * - 执行生命周期 (启动、停止、重试)
 * - 任务进度追踪
 * - WebSocket 实时事件
 * - 轮询任务状态
 */

import { create } from 'zustand'
import type { RunStatus } from '../types'
import * as api from '../api'
import { ExecutionSocket } from '../api/executionSocket'

// ==================== 类型定义 ====================

/** 单个任务的执行状态 */
export interface TaskState {
  id: string
  nodeId: string
  kind: string
  label: string
  status: string
  progress: number
  startedAt?: string
  completedAt?: string
  error?: string
  result?: Record<string, unknown>
}

/** 单个节点的执行聚合状态 */
export interface NodeExecutionState {
  nodeId: string
  status: RunStatus
  taskCount: number
  completedCount: number
  failedCount: number
  startedAt?: string
  completedAt?: string
  duration?: number
}

/** 执行状态类型 */
export type ExecutionStatus = 'idle' | 'running' | 'completed' | 'failed' | 'cancelled'

/** WebSocket 连接状态 */
export type SocketStatus = 'disconnected' | 'connecting' | 'connected'

/** 执行事件 (来自 WebSocket) */
export type ExecutionEvent = api.ExecutionEvent

/** Store 状态定义 */
export interface ExecutionState {
  // --- 状态 ---
  executionId: string | null
  status: ExecutionStatus
  taskCount: number
  completedCount: number
  tasks: Map<string, TaskState>
  nodeStates: Map<string, NodeExecutionState>
  events: ExecutionEvent[]
  socketStatus: SocketStatus
  startTime: number | null

  // --- Actions ---
  startExecution: (workflowId: string) => Promise<void>
  stopExecution: () => Promise<void>
  retryNode: (nodeId: string) => Promise<void>
  addEvent: (event: ExecutionEvent) => void
  updateTaskState: (taskId: string, state: Partial<TaskState>) => void
  resetExecution: () => void
}

// ==================== 内部状态 ====================

/** 执行代次，用于防止过期的异步回调更新状态 */
let runGeneration = 0
let pollTimer: ReturnType<typeof setTimeout> | null = null
let currentSocket: ExecutionSocket | null = null

// ==================== Store ====================

const initialState = {
  executionId: null as string | null,
  status: 'idle' as ExecutionStatus,
  taskCount: 0,
  completedCount: 0,
  tasks: new Map<string, TaskState>(),
  nodeStates: new Map<string, NodeExecutionState>(),
  events: [] as ExecutionEvent[],
  socketStatus: 'disconnected' as SocketStatus,
  startTime: null as number | null,
}

export const useExecutionStore = create<ExecutionState>((set, get) => ({
  ...initialState,

  // --- 启动执行 ---
  startExecution: async (workflowId: string) => {
    const generation = ++runGeneration

    set({
      status: 'running',
      startTime: Date.now(),
      tasks: new Map(),
      nodeStates: new Map(),
      events: [],
      socketStatus: 'connecting',
    })

    try {
      // 调用后端 API 启动执行
      const execResult = await api.startExecution(workflowId)

      if (generation !== runGeneration) return

      set({
        executionId: execResult.id,
        taskCount: execResult.task_count,
      })

      // 连接 WebSocket 接收实时事件
      const socket = new ExecutionSocket(execResult.id)
      currentSocket = socket

      socket.onEvent((event) => {
        if (generation !== runGeneration) return
        get().addEvent(event)
      })

      socket.onStatusChange((status) => {
        set({ socketStatus: status })
      })

      socket.connect()

      // 开始轮询任务状态
      pollExecutionState(generation, get)
    } catch (err) {
      console.error('启动执行失败:', err)
      set({
        status: 'failed',
        startTime: null,
      })
    }
  },

  // --- 停止执行 ---
  stopExecution: async () => {
    runGeneration += 1

    // 清除轮询定时器
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }

    // 断开 WebSocket
    if (currentSocket) {
      currentSocket.disconnect()
      currentSocket = null
    }

    // 调用后端取消 API
    const { executionId } = get()
    if (executionId) {
      try {
        await api.cancelExecution(executionId)
      } catch (err) {
        console.warn('取消执行失败:', err)
      }
    }

    set({ status: 'cancelled' })
  },

  // --- 重试单个节点 ---
  retryNode: async (nodeId: string) => {
    const { executionId, nodeStates } = get()
    if (!executionId) {
      console.warn('无活跃执行，无法重试节点')
      return
    }

    // 检查节点状态，只有 failed 节点可重试
    const nodeState = nodeStates.get(nodeId)
    if (nodeState && nodeState.status !== 'failed') {
      console.warn(`节点 ${nodeId} 状态为 ${nodeState.status}，无需重试`)
      return
    }

    try {
      await api.retryExecution(executionId, nodeId)

      // 更新节点状态为 waiting，等待 Worker 重新调度
      const updatedNodeStates = new Map(nodeStates)
      const existing = updatedNodeStates.get(nodeId)
      if (existing) {
        updatedNodeStates.set(nodeId, { ...existing, status: 'waiting', failedCount: 0 })
      }

      useExecutionStore.setState({ nodeStates: updatedNodeStates })
    } catch (err) {
      console.error(`节点 ${nodeId} 重试失败:`, err)
      throw err
    }
  },

  // --- 添加执行事件 ---
  addEvent: (event: ExecutionEvent) => {
    set((state) => {
      const events = [...state.events, event]
      const nodeStates = new Map(state.nodeStates)
      const tasks = new Map(state.tasks)

      // 更新节点状态
      if (event.node_id && event.type.startsWith('node.')) {
        const existing = nodeStates.get(event.node_id) ?? {
          nodeId: event.node_id,
          status: 'waiting' as RunStatus,
          taskCount: 0,
          completedCount: 0,
          failedCount: 0,
        }

        let newStatus: RunStatus = existing.status
        if (event.type === 'node.started') newStatus = 'running'
        else if (event.type === 'node.completed') newStatus = 'completed'
        else if (event.type === 'node.failed') newStatus = 'failed'

        nodeStates.set(event.node_id, { ...existing, status: newStatus })
      }

      // 处理任务进度事件
      if (event.type === 'task.started' && event.item_key) {
        const existing = tasks.get(event.item_key) ?? {
          id: event.item_key,
          nodeId: event.node_id,
          kind: '',
          label: event.item_key,
          status: 'running',
          progress: 0,
        }
        tasks.set(event.item_key, { ...existing, status: 'running', startedAt: event.timestamp })
      }

      if (event.type === 'task.completed' && event.item_key) {
        const existing = tasks.get(event.item_key)
        if (existing) {
          tasks.set(event.item_key, { ...existing, status: 'completed', progress: 100, completedAt: event.timestamp })
        }
      }

      // 计算已完成任务数
      let completedCount = 0
      tasks.forEach((task) => {
        if (task.status === 'completed') completedCount++
      })

      // 处理执行完成/失败
      let newStatus: ExecutionStatus = state.status
      if (event.type === 'execution.completed') {
        newStatus = 'completed'
      } else if (event.type === 'execution.failed') {
        newStatus = 'failed'
      }

      return { events, nodeStates, tasks, completedCount, status: newStatus }
    })
  },

  // --- 更新任务状态 ---
  updateTaskState: (taskId: string, partial: Partial<TaskState>) => {
    set((state) => {
      const tasks = new Map(state.tasks)
      const existing = tasks.get(taskId)
      if (existing) {
        tasks.set(taskId, { ...existing, ...partial })
      }
      return { tasks }
    })
  },

  // --- 重置执行状态 ---
  resetExecution: () => {
    runGeneration += 1
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
    if (currentSocket) {
      currentSocket.disconnect()
      currentSocket = null
    }
    set({ ...initialState })
  },
}))

// ==================== 轮询逻辑 ====================

/**
 * 轮询后端获取最新任务状态，更新 nodeStates 和 tasks。
 */
async function pollExecutionState(generation: number, get: () => ExecutionState) {
  const pollLoop = async () => {
    const current = get()
    if (!current.executionId || generation !== runGeneration) return

    try {
      const taskResponses = await api.getExecutionTasks(current.executionId)
      if (generation !== runGeneration) return

      const tasks = new Map<string, TaskState>()
      let completedCount = 0

      for (const task of taskResponses) {
        const existing = current.tasks.get(task.id)
        tasks.set(task.id, {
          id: task.id,
          nodeId: task.node_id,
          kind: task.kind,
          label: task.label,
          status: task.status,
          progress: existing?.progress ?? 0,
          startedAt: existing?.startedAt,
          completedAt: existing?.completedAt,
          error: task.error,
          result: task.result,
        })
        if (task.status === 'completed') completedCount++
      }

      // 聚合节点状态
      const nodeStates = new Map<string, NodeExecutionState>()
      const now = current.startTime

      for (const node of get().nodeStates.values()) {
        nodeStates.set(node.nodeId, node)
      }

      for (const task of taskResponses) {
        const existing = nodeStates.get(task.node_id) ?? {
          nodeId: task.node_id,
          status: 'waiting' as RunStatus,
          taskCount: 0,
          completedCount: 0,
          failedCount: 0,
        }

        const nodeTasks = taskResponses.filter((t) => t.node_id === task.node_id)
        const allCompleted = nodeTasks.every((t) => t.status === 'completed')
        const anyFailed = nodeTasks.some((t) => t.status === 'failed')
        const anyRunning = nodeTasks.some((t) => t.status === 'running')

        let status: RunStatus = existing.status
        if (allCompleted) status = 'completed'
        else if (anyFailed) status = 'failed'
        else if (anyRunning) status = 'running'

        nodeStates.set(task.node_id, {
          ...existing,
          status,
          taskCount: nodeTasks.length,
          completedCount: nodeTasks.filter((t) => t.status === 'completed').length,
          failedCount: nodeTasks.filter((t) => t.status === 'failed').length,
          duration: now ? Date.now() - now : 0,
        })
      }

      useExecutionStore.setState({ tasks, nodeStates, completedCount })

      // 检查执行是否结束
      const execStatus = await api.getExecution(current.executionId)
      if (generation !== runGeneration) return

      if (execStatus.status === 'completed' || execStatus.status === 'failed') {
        useExecutionStore.setState({ status: execStatus.status as ExecutionStatus })
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

  pollLoop()
}
