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
import type { EdgeData, EdgeMode, EnhancedEdge, FieldDefinition, NodeKind, PortInfo, RunStatus, StudioNode, WorkflowSpec } from './types'

const STORAGE_KEY = 'ai-video-create.workflow.v1'
const MAX_HISTORY = 50
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

// ==================== Connection Session ====================

export interface ConnectingFrom {
  nodeId: string
  handleId: string
  portType: string
}

export interface ErrorTarget {
  nodeId: string
  handleId: string
}

// ==================== 状态接口 ====================

interface WorkflowState {
  workflow: WorkflowSpec
  selectedNodeId: string | null
  selectedNodeIds: string[]
  focusedNodeId: string | null
  selectedEdgeId: string | null
  serverVersion: number | null
  isDirty: boolean

  // History
  past: WorkflowSpec[]
  future: WorkflowSpec[]

  // Clipboard (for copy/paste)
  copiedNodes: StudioNode[]
  copiedEdges: EnhancedEdge[]

  // Actions
  setWorkflow: (workflow: WorkflowSpec) => void
  onNodesChange: (changes: NodeChange<StudioNode>[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onConnect: (connection: Connection) => void
  selectNode: (id: string | null) => void
  selectNodeAdditive: (id: string) => void
  toggleNodeSelection: (id: string) => void
  selectAllNodes: () => void
  clearSelection: () => void
  focusNode: (id: string | null) => void
  nudgeSelectedNodes: (dx: number, dy: number) => void
  selectEdge: (id: string | null) => void
  updateEdgeData: (edgeId: string, data: Partial<EdgeData>) => void
  reconnectEdge: (edgeId: string, newSource: string, newTarget: string, newSourceHandle: string, newTargetHandle: string) => void
  deleteSelectedEdge: () => void
  deleteSelectedNodes: () => void
  updateConfig: (key: string, value: string | number | boolean) => void
  undo: () => void
  redo: () => void
  canUndo: () => boolean
  canRedo: () => boolean
  saveToServer: () => Promise<void>
  loadFromServer: (id?: string) => Promise<void>
  serverSync: () => void

  // Copy / Paste
  copySelectedNodes: () => void
  pasteNodes: () => void

  // Viewport persistence
  saveViewport: (viewport: { x: number; y: number; zoom: number }) => void

  // Auto layout
  applyAutoLayout: (positions: Map<string, { x: number; y: number }>) => void

  // Connection error feedback
  connectionError: string | null
  setConnectionError: (msg: string | null) => void

  // Connection session — tracks active drag from source port
  connectingFrom: ConnectingFrom | null
  setConnectingFrom: (info: ConnectingFrom | null) => void

  // Error target — port that was rejected
  errorTarget: ErrorTarget | null
  setErrorTarget: (target: ErrorTarget | null) => void

  // Field management
  addField: (nodeId: string, field: FieldDefinition) => void
  updateField: (nodeId: string, fieldId: string, field: FieldDefinition) => void
  removeField: (nodeId: string, fieldId: string) => void
  deleteField: (nodeId: string, fieldId: string) => void
  reorderFields: (nodeId: string, fromIndex: number, toIndex: number) => void
  duplicateField: (nodeId: string, fieldId: string) => void
  updateFieldConfig: (key: string, value: string | number | boolean) => void

  // Port management
  addPort: (nodeId: string, direction: 'input' | 'output', port: PortInfo) => void
  updatePort: (nodeId: string, direction: 'input' | 'output', portId: string, port: PortInfo) => void
  deletePort: (nodeId: string, direction: 'input' | 'output', portId: string) => void

  // 节点状态更新 (供 executionStore 调用)
  updateNodeStatus: (nodeId: string, status: RunStatus) => void
  updateNodeStatuses: (statuses: Map<string, RunStatus>) => void
  resetNodeStatuses: () => void
  ensureSavedToServer: () => Promise<boolean>

  // --- Semantic history batching ---
  beginBatchHistory: (preDragWorkflow: WorkflowSpec) => void
  endBatchHistory: () => void
}

// ==================== 内部工具 ====================

let saveTimer: ReturnType<typeof setTimeout> | null = null

function pushHistory(state: WorkflowState, workflow: WorkflowSpec): Pick<WorkflowState, 'past' | 'future'> {
  const past = [...state.past, state.workflow].slice(-MAX_HISTORY)
  return { past, future: [] }
}

// ==================== Semantic history batching ====================
// Groups rapid successive changes (e.g. continuous node drag) into one undo step.

interface BatchState {
  /** Workflow snapshot captured before the batch began (pre-drag state). */
  preDragWorkflow: WorkflowSpec
  /** Whether a batch session is currently active. */
  active: boolean
}

let _batchState: BatchState | null = null

/**
 * Begin a history batch session. Must be called with the workflow state
 * *before* the first in-progress change arrives (i.e. on drag start).
 */
function beginBatchHistory(preDragWorkflow: WorkflowSpec) {
  _batchState = { preDragWorkflow, active: true }
}

/**
 * End the current batch session and push a single history entry
 * representing the pre-batch state.
 */
function endBatchHistory() {
  if (!_batchState?.active) {
    _batchState = null
    return
  }
  const snapshot = _batchState.preDragWorkflow
  _batchState = null
  // We push to past/future directly here so the next set() call
  // from the caller can include it in the state update.
  _pendingBatchPush = snapshot
}

/**
 * After endBatchHistory(), the caller should read and clear this value
 * to include the batch push in its state update.
 */
let _pendingBatchPush: WorkflowSpec | null = null

function consumePendingBatchPush(): WorkflowSpec | null {
  const v = _pendingBatchPush
  _pendingBatchPush = null
  return v
}

/** Generate a short unique ID for pasted nodes/edges */
function uid(): string {
  return crypto.randomUUID().slice(0, 8)
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
  selectedNodeIds: [],
  focusedNodeId: null,
  selectedEdgeId: null,
  serverVersion: null,
  isDirty: false,
  connectionError: null,
  connectingFrom: null,
  errorTarget: null,
  copiedNodes: [],
  copiedEdges: [],
  past: [],
  future: [],

  saveViewport: (viewport) => set((state) => {
    const workflow = { ...state.workflow, viewport }
    persistLocal(workflow)
    return { workflow }
  }),

  applyAutoLayout: (positions) => set((state) => {
    const nodes = state.workflow.nodes.map((node) => {
      const pos = positions.get(node.id)
      if (!pos) return node
      return { ...node, position: pos }
    })
    const workflow = { ...state.workflow, nodes }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  setWorkflow: (workflow) => {
    // Run graph validation on the incoming workflow
    const errors = validateGraph(workflow.nodes, workflow.edges, NODE_CATALOG)
    if (errors.length > 0) {
      console.warn('Graph validation issues:', errors)
    }
    const history = pushHistory(get(), workflow)
    persistLocal(workflow)
    set({ workflow, selectedNodeId: null, selectedNodeIds: [], focusedNodeId: null, selectedEdgeId: null, isDirty: true, ...history })
    scheduleSave(get)
  },

  onNodesChange: (changes) => set((state) => {
    const workflow = { ...state.workflow, nodes: applyNodeChanges(changes, state.workflow.nodes) }

    // During a batch session, position changes update state but do NOT push history.
    // Non-position changes (selection, removal, etc.) still push history normally.
    const isBatchPositionChange = _batchState?.active
      && changes.every(c => c.type === 'position')

    const history = isBatchPositionChange ? { past: state.past, future: state.future } : pushHistory(state, workflow)
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
      return {
        ...state,
        connectionError: error.message,
        errorTarget: { nodeId: connection.target, handleId: connection.targetHandle ?? '' },
      }
    }

    const newEdge = {
      ...connection,
      // type omitted → uses 'default' → our custom LabelEdge (smoothstep path)
      data: { mode: 'direct' as const, label: '' },
    }
    const workflow = { ...state.workflow, edges: addEdge(newEdge, state.workflow.edges) }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, connectionError: null, connectingFrom: null, errorTarget: null, ...history }
  }),

  selectNode: (selectedNodeId) => set({ selectedNodeId, selectedNodeIds: selectedNodeId ? [selectedNodeId] : [], selectedEdgeId: null }),

  selectNodeAdditive: (id) => set((state) => {
    const ids = state.selectedNodeIds.includes(id)
      ? state.selectedNodeIds
      : [...state.selectedNodeIds, id]
    return { selectedNodeIds: ids, selectedNodeId: ids[0] ?? null, selectedEdgeId: null }
  }),

  toggleNodeSelection: (id) => set((state) => {
    const idx = state.selectedNodeIds.indexOf(id)
    const ids = idx >= 0
      ? state.selectedNodeIds.filter((n) => n !== id)
      : [...state.selectedNodeIds, id]
    return { selectedNodeIds: ids, selectedNodeId: ids[0] ?? null, selectedEdgeId: null }
  }),

  selectAllNodes: () => set((state) => {
    const ids = state.workflow.nodes.map((n) => n.id)
    return { selectedNodeIds: ids, selectedNodeId: ids[0] ?? null, selectedEdgeId: null }
  }),

  clearSelection: () => set({ selectedNodeId: null, selectedNodeIds: [], selectedEdgeId: null }),

  focusNode: (id) => set({ focusedNodeId: id }),

  nudgeSelectedNodes: (dx, dy) => set((state) => {
    const ids = new Set(state.selectedNodeIds)
    if (ids.size === 0) return state
    const nodes = state.workflow.nodes.map((n) =>
      ids.has(n.id)
        ? { ...n, position: { x: n.position.x + dx, y: n.position.y + dy } }
        : n,
    )
    const workflow = { ...state.workflow, nodes }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  selectEdge: (selectedEdgeId) => set({ selectedEdgeId, selectedNodeId: null, selectedNodeIds: [] }),

  updateEdgeData: (edgeId, data) => set((state) => {
    const edges = state.workflow.edges.map((edge) =>
      edge.id === edgeId
        ? { ...edge, data: { ...edge.data, ...data } }
        : edge,
    )
    const workflow = { ...state.workflow, edges }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  reconnectEdge: (edgeId, newSource, newTarget, newSourceHandle, newTargetHandle) => set((state) => {
    const edge = state.workflow.edges.find((e) => e.id === edgeId)
    if (!edge) return state

    // Validate the new connection
    const nodeKinds: Record<string, NodeKind> = {}
    state.workflow.nodes.forEach(n => { nodeKinds[n.id] = n.data.kind })

    // Check for duplicates (excluding the current edge being reconnected)
    const otherEdges = state.workflow.edges.filter((e) => e.id !== edgeId)
    const error = validateConnectionNew(
      newSource, newSourceHandle, newTarget, newTargetHandle,
      nodeKinds, NODE_CATALOG, otherEdges,
    )
    if (error) {
      console.warn('Reconnect rejected:', error.message)
      return { ...state, connectionError: error.message }
    }

    const edges = state.workflow.edges.map((e) =>
      e.id === edgeId
        ? { ...e, source: newSource, target: newTarget, sourceHandle: newSourceHandle, targetHandle: newTargetHandle }
        : e,
    )
    const workflow = { ...state.workflow, edges }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, connectionError: null, ...history }
  }),

  deleteSelectedEdge: () => set((state) => {
    if (!state.selectedEdgeId) return state
    const edges = state.workflow.edges.filter((e) => e.id !== state.selectedEdgeId)
    const workflow = { ...state.workflow, edges }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, selectedEdgeId: null, isDirty: true, ...history }
  }),

  deleteSelectedNodes: () => set((state) => {
    const ids = state.selectedNodeIds
    if (ids.length === 0) return state
    const idSet = new Set(ids)
    const nodes = state.workflow.nodes.filter((n) => !idSet.has(n.id))
    const edges = state.workflow.edges.filter((e) => !idSet.has(e.source) && !idSet.has(e.target))
    const workflow = { ...state.workflow, nodes, edges }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, selectedNodeId: null, selectedNodeIds: [], selectedEdgeId: null, isDirty: true, ...history }
  }),

  setConnectionError: (msg) => set((state) => ({
    connectionError: msg,
    errorTarget: msg === null ? null : state.errorTarget,
  })),

  setConnectingFrom: (info) => set({ connectingFrom: info }),

  setErrorTarget: (target) => set({ errorTarget: target }),

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

  // --- Port management ---
  addPort: (nodeId, direction, port) => set((state) => {
    const nodes = state.workflow.nodes.map((node) => {
      if (node.id !== nodeId) return node
      const ports = node.data.ports ?? { inputs: [], outputs: [] }
      const list = direction === 'input' ? ports.inputs : ports.outputs
      const newPorts = {
        inputs: direction === 'input' ? [...list, port] : ports.inputs,
        outputs: direction === 'output' ? [...list, port] : ports.outputs,
      }
      return { ...node, data: { ...node.data, ports: newPorts } }
    })
    const workflow = { ...state.workflow, nodes }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  updatePort: (nodeId, direction, portId, port) => set((state) => {
    const nodes = state.workflow.nodes.map((node) => {
      if (node.id !== nodeId) return node
      const ports = node.data.ports ?? { inputs: [], outputs: [] }
      const list = direction === 'input' ? ports.inputs : ports.outputs
      const updated = list.map((p) => p.id === portId ? port : p)
      const newPorts = {
        inputs: direction === 'input' ? updated : ports.inputs,
        outputs: direction === 'output' ? updated : ports.outputs,
      }
      return { ...node, data: { ...node.data, ports: newPorts } }
    })
    const workflow = { ...state.workflow, nodes }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  deletePort: (nodeId, direction, portId) => set((state) => {
    // Compute affected edges from current state snapshot
    const affectedEdgeIds = state.workflow.edges
      .filter((e) =>
        (e.source === nodeId && e.sourceHandle === portId) ||
        (e.target === nodeId && e.targetHandle === portId),
      )
      .map((e) => e.id)

    const nodes = state.workflow.nodes.map((node) => {
      if (node.id !== nodeId) return node
      const ports = node.data.ports ?? { inputs: [], outputs: [] }
      const list = direction === 'input' ? ports.inputs : ports.outputs
      const filtered = list.filter((p) => p.id !== portId)
      const newPorts = {
        inputs: direction === 'input' ? filtered : ports.inputs,
        outputs: direction === 'output' ? filtered : ports.outputs,
      }
      return { ...node, data: { ...node.data, ports: newPorts } }
    })

    // Cascade-delete associated edges
    const edges = state.workflow.edges.filter((e) => !affectedEdgeIds.includes(e.id))
    const workflow = { ...state.workflow, nodes, edges }
    const history = pushHistory(state, workflow)
    persistLocal(workflow)
    return { workflow, isDirty: true, ...history }
  }),

  // --- Copy / Paste ---
  copySelectedNodes: () => set((state) => {
    const ids = new Set(state.selectedNodeIds)
    if (ids.size === 0) return state
    const nodes = state.workflow.nodes.filter((n) => ids.has(n.id))
    // Only include edges where BOTH source and target are in the selection
    const edges = state.workflow.edges.filter((e) => ids.has(e.source) && ids.has(e.target))
    return { copiedNodes: nodes, copiedEdges: edges }
  }),

  pasteNodes: () => set((state) => {
    const { copiedNodes, copiedEdges, workflow } = state
    if (copiedNodes.length === 0) return state

    const PASTE_OFFSET = 40
    // Build oldId -> newId mapping
    const idMap = new Map<string, string>()
    const newNodes: StudioNode[] = copiedNodes.map((node) => {
      const newId = `${node.data.kind}-${uid()}`
      idMap.set(node.id, newId)
      return {
        ...node,
        id: newId,
        position: { x: node.position.x + PASTE_OFFSET, y: node.position.y + PASTE_OFFSET },
        selected: false,
      }
    })

    const newEdges: EnhancedEdge[] = copiedEdges.map((edge) => {
      const newSource = idMap.get(edge.source) ?? edge.source
      const newTarget = idMap.get(edge.target) ?? edge.target
      return {
        ...edge,
        id: `edge-${uid()}`,
        source: newSource,
        target: newTarget,
      }
    })

    const updatedWorkflow = {
      ...workflow,
      nodes: [...workflow.nodes, ...newNodes],
      edges: [...workflow.edges, ...newEdges],
    }
    const history = pushHistory(state, updatedWorkflow)
    persistLocal(updatedWorkflow)
    const pastedIds = newNodes.map((n) => n.id)
    return {
      workflow: updatedWorkflow,
      selectedNodeId: pastedIds[0] ?? null,
      selectedNodeIds: pastedIds,
      isDirty: true,
      ...history,
    }
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
    return { workflow: previous, past, future: [state.workflow, ...state.future], selectedNodeId: null, selectedNodeIds: [], focusedNodeId: null, selectedEdgeId: null }
  }),

  redo: () => set((state) => {
    if (state.future.length === 0) return state
    const next = state.future[0]
    const future = state.future.slice(1)
    persistLocal(next)
    return { workflow: next, past: [...state.past, state.workflow], future, selectedNodeId: null, selectedNodeIds: [], focusedNodeId: null, selectedEdgeId: null }
  }),

  canUndo: () => get().past.length > 0,
  canRedo: () => get().future.length > 0,

  // --- Semantic history batching ---
  beginBatchHistory: (preDragWorkflow) => {
    beginBatchHistory(preDragWorkflow)
  },

  endBatchHistory: () => {
    endBatchHistory()
    const snapshot = consumePendingBatchPush()
    if (snapshot) {
      set((state) => {
        const past = [...state.past, snapshot].slice(-MAX_HISTORY)
        persistLocal(state.workflow)
        return { past, future: [] }
      })
    }
  },

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
