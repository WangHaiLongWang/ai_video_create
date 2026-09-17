/**
 * workflowStore — 工作流画布与历史状态管理
 *
 * 职责:
 * - 画布节点、边的增删改查
 * - 选择节点
 * - 撤销/重做历史
 * - 自动保存到本地和服务器
 *
 * 执行相关逻辑已拆分至 stores/executionStore.ts
 */

import { addEdge, applyEdgeChanges, applyNodeChanges, type Connection, type EdgeChange, type NodeChange } from '@xyflow/react'
import { create } from 'zustand'
import * as api from './api'
import { createPromptToVideoWorkflow } from './workflow'
import { validateConnection as validateConnectionNew, validateGraph } from './schemas/graph-validation'
import { NODE_CATALOG } from './schemas/node-manifest'
import { upgradeWorkflowSpec } from './schemas/workflow-spec'
import type { FieldDefinition, NodeKind, RunStatus, StudioNode, WorkflowSpec } from './types'

const STORAGE_KEY = 'ai-video-create.workflow.v1'
const MAX_HISTORY = 30
const SAVE_DEBOUNCE_MS = 1000

function initialWorkflow(): WorkflowSpec {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      return upgradeWorkflowSpec(parsed)
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY)
  }
  return createPromptToVideoWorkflow() as unknown as WorkflowSpec
}

function persistLocal(workflow: WorkflowSpec) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(workflow))
}

// ==================== 状态接口 ====================

interface WorkflowState {
  workflow: WorkflowSpec
  selectedNodeId: string | null
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
  undo: () => void
  redo: () => void
  canUndo: () => boolean
  canRedo: () => boolean
  saveToServer: () => Promise<void>
  loadFromServer: (id?: string) => Promise<void>
  serverSync: () => void

  // Connection error feedback
  connectionError: string | null
  setConnectionError: (msg: string | null) => void

  // Field management
  addField: (nodeId: string, field: FieldDefinition) => void
  updateField: (nodeId: string, fieldId: string, field: FieldDefinition) => void
  removeField: (nodeId: string, fieldId: string) => void
  deleteField: (nodeId: string, fieldId: string) => void
  reorderFields: (nodeId: string, fromIndex: number, toIndex: number) => void
  duplicateField: (nodeId: string, fieldId: string) => void
  updateFieldConfig: (key: string, value: string | number | boolean) => void

  // 节点状态更新 (供 executionStore 调用)
  updateNodeStatus: (nodeId: string, status: RunStatus) => void
  updateNodeStatuses: (statuses: Map<string, RunStatus>) => void
  resetNodeStatuses: () => void
  ensureSavedToServer: () => Promise<boolean>
}

// ==================== 内部工具 ====================

let saveTimer: ReturnType<typeof setTimeout> | null = null

function pushHistory(state: WorkflowState, workflow: WorkflowSpec): Pick<WorkflowState, 'past' | 'future'> {
  const past = [...state.past, state.workflow].slice(-MAX_HISTORY)
  return { past, future: [] }
}

function scheduleSave(get: () => WorkflowState) {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    get().saveToServer()
  }, SAVE_DEBOUNCE_MS)
}

// ==================== Store ====================

export const useStudioStore = create<WorkflowState>((set, get) => ({
  workflow: initialWorkflow(),
  selectedNodeId: null,
  serverVersion: null,
  isDirty: false,
  connectionError: null,
  past: [],
  future: [],

  setWorkflow: (workflow) => {
    // Run graph validation on the incoming workflow
    const errors = validateGraph(workflow.nodes, workflow.edges, NODE_CATALOG)
    if (errors.length > 0) {
      console.warn('Graph validation issues:', errors)
    }
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
    if (!source || !target || !connection.sourceHandle || !connection.targetHandle) return state

    // Build nodeKinds map for catalog-based validation
    const nodeKinds: Record<string, NodeKind> = {}
    state.workflow.nodes.forEach(n => { nodeKinds[n.id] = n.data.kind })

    const error = validateConnectionNew(
      connection.source, connection.sourceHandle,
      connection.target, connection.targetHandle,
      nodeKinds, NODE_CATALOG, state.workflow.edges,
    )
    if (error) {
      console.warn('Connection rejected:', error.message)
      return { ...state, connectionError: error.message }
    }

    const newEdge = {
      ...connection,
      // type omitted → uses 'default' → our custom LabelEdge (smoothstep path)
      data: { mode: 'direct' as const, label: '' },
    }
    const workflow = { ...state.workflow, edges: addEdge(newEdge, state.workflow.edges) }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, connectionError: null, ...history }
  }),

  selectNode: (selectedNodeId) => set({ selectedNodeId }),

  setConnectionError: (msg) => set({ connectionError: msg }),

  updateConfig: (key, value) => set((state) => {
    const nodes = state.workflow.nodes.map((node) => node.id === state.selectedNodeId
      ? { ...node, data: { ...node.data, config: { ...node.data.config, [key]: value } } }
      : node)
    const workflow = { ...state.workflow, nodes }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  // --- Field management ---
  addField: (nodeId, field) => set((state) => {
    const nodes = state.workflow.nodes.map((node) => {
      if (node.id !== nodeId) return node
      const schema = node.data.fieldSchema ?? []
      const newSchema = [...schema, field]
      const newConfig = { ...node.data.config }
      if (field.default !== undefined) {
        newConfig[field.id] = field.default
      }
      return { ...node, data: { ...node.data, fieldSchema: newSchema, config: newConfig } }
    })
    const workflow = { ...state.workflow, nodes }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  updateField: (nodeId, fieldId, field) => set((state) => {
    const nodes = state.workflow.nodes.map((node) => {
      if (node.id !== nodeId) return node
      const schema = node.data.fieldSchema ?? []
      const newSchema = schema.map((f) => f.id === fieldId ? field : f)
      return { ...node, data: { ...node.data, fieldSchema: newSchema } }
    })
    const workflow = { ...state.workflow, nodes }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  removeField: (nodeId, fieldId) => set((state) => {
    const nodes = state.workflow.nodes.map((node) => {
      if (node.id !== nodeId) return node
      const schema = node.data.fieldSchema ?? []
      const newSchema = schema.filter((f) => f.id !== fieldId)
      const newConfig = { ...node.data.config }
      delete newConfig[fieldId]
      return { ...node, data: { ...node.data, fieldSchema: newSchema, config: newConfig } }
    })
    const workflow = { ...state.workflow, nodes }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  deleteField: (nodeId, fieldId) => set((state) => {
    const nodes = state.workflow.nodes.map((node) => {
      if (node.id !== nodeId) return node
      const schema = node.data.fieldSchema ?? []
      const field = schema.find((f) => f.id === fieldId)
      if (!field) return node
      const newSchema = schema.filter((f) => f.id !== fieldId)
      const newConfig = { ...node.data.config }
      delete newConfig[fieldId]
      return { ...node, data: { ...node.data, fieldSchema: newSchema, config: newConfig } }
    })
    const workflow = { ...state.workflow, nodes }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  reorderFields: (nodeId, fromIndex, toIndex) => set((state) => {
    const nodes = state.workflow.nodes.map((node) => {
      if (node.id !== nodeId) return node
      const schema = [...(node.data.fieldSchema ?? [])]
      const [moved] = schema.splice(fromIndex, 1)
      if (!moved) return node
      schema.splice(toIndex, 0, moved)
      return { ...node, data: { ...node.data, fieldSchema: schema } }
    })
    const workflow = { ...state.workflow, nodes }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  duplicateField: (nodeId, fieldId) => set((state) => {
    const nodes = state.workflow.nodes.map((node) => {
      if (node.id !== nodeId) return node
      const schema = node.data.fieldSchema ?? []
      const fieldIndex = schema.findIndex((f) => f.id === fieldId)
      if (fieldIndex === -1) return node
      const original = schema[fieldIndex]
      const newId = original.id + '_copy'
      const duplicate: FieldDefinition = {
        ...original,
        id: newId,
        label: original.label + ' (副本)',
      }
      const newSchema = [...schema]
      newSchema.splice(fieldIndex + 1, 0, duplicate)
      const newConfig = { ...node.data.config }
      if (duplicate.default !== undefined) {
        newConfig[duplicate.id] = duplicate.default
      }
      return { ...node, data: { ...node.data, fieldSchema: newSchema, config: newConfig } }
    })
    const workflow = { ...state.workflow, nodes }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  updateFieldConfig: (key, value) => set((state) => {
    const nodes = state.workflow.nodes.map((node) => node.id === state.selectedNodeId
      ? { ...node, data: { ...node.data, config: { ...node.data.config, [key]: value } } }
      : node)
    const workflow = { ...state.workflow, nodes }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  // --- 节点状态更新 (供 executionStore 调用) ---
  updateNodeStatus: (nodeId, status) => set((state) => ({
    workflow: {
      ...state.workflow,
      nodes: state.workflow.nodes.map((node) =>
        node.id === nodeId
          ? { ...node, data: { ...node.data, status } }
          : node,
      ),
    },
  })),

  updateNodeStatuses: (statuses) => set((state) => ({
    workflow: {
      ...state.workflow,
      nodes: state.workflow.nodes.map((node) => {
        const status = statuses.get(node.id)
        if (status !== undefined) {
          return { ...node, data: { ...node.data, status } }
        }
        return node
      }),
    },
  })),

  resetNodeStatuses: () => set((state) => ({
    workflow: {
      ...state.workflow,
      nodes: state.workflow.nodes.map((node) => ({
        ...node,
        data: { ...node.data, status: 'idle' as RunStatus },
      })),
    },
  })),

  // --- 确保工作流已保存到服务器 (执行前调用) ---
  ensureSavedToServer: async () => {
    const { workflow, serverVersion, isDirty } = get()
    try {
      if (serverVersion === null) {
        const result = await api.createWorkflow(workflow as unknown as Record<string, unknown>)
        set({ serverVersion: result.version, isDirty: false })
      } else if (isDirty) {
        const result = await api.updateWorkflow(
          workflow.id,
          workflow as unknown as Record<string, unknown>,
          serverVersion,
        )
        set({ serverVersion: result.version, isDirty: false })
      }
      return true
    } catch (err) {
      console.error('保存工作流到服务器失败:', err)
      return false
    }
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
        const spec = upgradeWorkflowSpec(detail.spec)
        persistLocal(spec)
        set({ workflow: spec, serverVersion: detail.version, isDirty: false, past: [], future: [] })
      } else {
        const list = await api.fetchWorkflows()
        if (list.length > 0) {
          const latest = list[0]
          const detail = await api.getWorkflow(latest.id)
          const spec = upgradeWorkflowSpec(detail.spec)
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
