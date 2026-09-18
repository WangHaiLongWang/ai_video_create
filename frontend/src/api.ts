/**
 * API 客户端 — 与后端 Workflow CRUD、执行、Agent、模板交互。
 */

import type { WorkflowSpec } from './types'
export type { WorkflowSpec } from './types'

const API_BASE = '/api'

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `请求失败 (${res.status})`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// ==================== Workflow CRUD ====================

export interface WorkflowSummary {
  id: string
  name: string
  description: string
  version: number
  created_at: string
  updated_at: string
}

export interface WorkflowDetail extends WorkflowSummary {
  spec: Record<string, unknown>
}

export function fetchWorkflows(): Promise<WorkflowSummary[]> {
  return apiRequest('/workflows')
}

export function getWorkflow(id: string): Promise<WorkflowDetail> {
  return apiRequest(`/workflows/${id}`)
}

export function createWorkflow(spec: Record<string, unknown>): Promise<WorkflowSummary> {
  return apiRequest('/workflows', { method: 'POST', body: JSON.stringify(spec) })
}

export function updateWorkflow(
  id: string,
  spec: Record<string, unknown>,
  expectedVersion: number,
): Promise<WorkflowSummary> {
  return apiRequest(`/workflows/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ spec, expected_version: expectedVersion }),
  })
}

export function deleteWorkflow(id: string): Promise<void> {
  return apiRequest(`/workflows/${id}`, { method: 'DELETE' })
}

export function duplicateWorkflow(id: string, name?: string): Promise<WorkflowSummary> {
  return apiRequest(`/workflows/${id}/duplicate`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export function exportWorkflow(id: string): Promise<{ spec: Record<string, unknown> }> {
  return apiRequest(`/workflows/${id}/export`, { method: 'POST' })
}

export function importWorkflow(spec: Record<string, unknown>): Promise<WorkflowSummary> {
  return apiRequest('/workflows/import', { method: 'POST', body: JSON.stringify(spec) })
}

// ==================== Execution ====================

export interface ExecutionResponse {
  id: string
  workflow_id: string
  status: string
  task_count: number
}

export interface TaskResponse {
  id: string
  node_id: string
  kind: string
  label: string
  status: string
  result?: Record<string, unknown>
  error?: string
}

export interface ExecutionEvent {
  event_id?: string
  execution_id: string
  node_id: string
  type: string
  status: string
  progress: number
  message: string
  item_key?: string
  timestamp: string
}

export function startExecution(workflowId: string): Promise<ExecutionResponse> {
  return apiRequest(`/executions/${workflowId}/start`, { method: 'POST' })
}

export function getExecution(executionId: string): Promise<ExecutionResponse> {
  return apiRequest(`/executions/${executionId}`)
}

export function getExecutionTasks(executionId: string): Promise<TaskResponse[]> {
  return apiRequest(`/executions/${executionId}/tasks`)
}

export function cancelExecution(executionId: string): Promise<void> {
  return apiRequest(`/executions/${executionId}/cancel`, { method: 'POST' })
}

export function retryExecution(executionId: string, nodeId: string): Promise<{
  execution_id: string
  task_id: string
  node_id: string
  status: string
  idempotency_key: string | null
  message: string
}> {
  return apiRequest(`/executions/${executionId}/retry`, {
    method: 'POST',
    body: JSON.stringify({ node_id: nodeId }),
  })
}

export function getExecutionEvents(executionId: string): Promise<ExecutionEvent[]> {
  return apiRequest(`/executions/${executionId}/events`)
}

// ==================== Agent ====================

export interface AgentGenerateRequest {
  prompt: string
  scenes?: number
  style?: string
}

export interface AgentModifyRequest {
  workflow_id: string
  instruction: string
}

export interface AgentExplainRequest {
  workflow_id: string
}

export interface GraphPatch {
  description: string
  add_nodes: Record<string, unknown>[]
  remove_nodes: string[]
  update_nodes: Record<string, unknown>[]
  add_edges: Record<string, unknown>[]
  remove_edges: string[]
}

// --- v1 preview response (legacy) ---

export interface AgentPreviewResponse {
  status: string
  spec?: WorkflowSpec
  patch?: GraphPatch
  diff?: string
  warnings: string[]
  destructive: boolean
  // v2 fields (AGENT-206)
  intent?: WorkflowIntent
  validation_errors?: ValidationError[]
  repair_steps?: RepairStep[]
  cost_estimate?: CostEstimate
  can_apply?: boolean
}

// --- v2 structured types ---

export interface PortRef {
  node: string
  port: string
}

export interface ConnectionIntent {
  source: PortRef
  target: PortRef
  mode: 'direct' | 'map' | 'aggregate'
}

export interface NodeIntent {
  alias: string
  kind: string
  config?: Record<string, unknown>
  label?: string
  description?: string
}

export interface WorkflowIntent {
  name: string
  description?: string
  template_id?: string
  nodes: NodeIntent[]
  connections: ConnectionIntent[]
  tags?: string[]
  scene_count?: number
  variant_count?: number
  duration?: number
  resolution?: string
  warnings?: string[]
}

export interface ValidationError {
  code: string
  message: string
  node?: string
  port?: string
  edge_index?: number
}

export interface RepairStep {
  attempt: number
  errors_before: ValidationError[]
  repairs_applied: string[]
  errors_after: ValidationError[]
}

export interface CostEstimate {
  scene_count: number
  variant_count: number
  image_calls: number
  video_calls: number
  storyboard_calls: number
  concat_calls: number
  total_calls: number
  estimated_duration_seconds: number
  warnings?: string[]
}

export interface AgentPreviewResponse_v2 {
  intent: WorkflowIntent
  compiled_workflow: WorkflowSpec | null
  validation_errors: ValidationError[]
  repair_steps: RepairStep[]
  cost_estimate: CostEstimate | null
  warnings: string[]
  can_apply: boolean
}

export interface AgentApplyResponse {
  success: boolean
  workflow_id?: string
  version?: number
  error?: string
}

export function agentGenerate(prompt: string, options?: { scenes?: number; style?: string }): Promise<WorkflowSpec> {
  return apiRequest('/agent/generate', {
    method: 'POST',
    body: JSON.stringify({ prompt, ...options }),
  })
}

export function agentGeneratePreview(prompt: string): Promise<AgentPreviewResponse> {
  return apiRequest('/agent/generate-preview', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  })
}

export function agentModify(workflowId: string, instruction: string): Promise<{ patch: GraphPatch }> {
  return apiRequest('/agent/modify', {
    method: 'POST',
    body: JSON.stringify({ workflow_id: workflowId, instruction }),
  })
}

export function agentModifyPreview(
  workflowId: string,
  instruction: string,
): Promise<AgentPreviewResponse> {
  return apiRequest('/agent/modify-preview', {
    method: 'POST',
    body: JSON.stringify({ workflow_id: workflowId, instruction }),
  })
}

export function agentExplain(workflowId: string): Promise<{ explanation: string }> {
  return apiRequest('/agent/explain', {
    method: 'POST',
    body: JSON.stringify({ workflow_id: workflowId }),
  })
}

export function agentApplyPatch(
  workflowId: string,
  patch: GraphPatch,
  expectedVersion?: number,
): Promise<WorkflowSpec> {
  return apiRequest('/agent/apply-patch', {
    method: 'POST',
    body: JSON.stringify({ workflow_id: workflowId, patch, expected_version: expectedVersion }),
  })
}

// --- v2 API (AGENT-211) ---

export function agentGeneratePreview_v2(prompt: string): Promise<AgentPreviewResponse_v2> {
  return apiRequest('/agent/generate-preview-v2', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  })
}

export function agentModifyPreview_v2(
  workflowId: string,
  instruction: string,
): Promise<AgentPreviewResponse_v2> {
  return apiRequest('/agent/modify-preview-v2', {
    method: 'POST',
    body: JSON.stringify({ workflow_id: workflowId, instruction }),
  })
}

export function agentApply_v2(
  intent: WorkflowIntent,
  options?: { workflowId?: string; expectedVersion?: number },
): Promise<AgentApplyResponse> {
  return apiRequest('/agent/apply-v2', {
    method: 'POST',
    body: JSON.stringify({
      intent,
      workflow_id: options?.workflowId ?? null,
      expected_version: options?.expectedVersion ?? null,
    }),
  })
}

// ==================== Templates ====================

export interface TemplateInfo {
  id: string
  name: string
  description: string
  node_count: number
  is_builtin: boolean
}

export type TemplateSummary = TemplateInfo

export interface TemplateDetail extends TemplateInfo {
  nodes: Record<string, unknown>[]
  edges: Record<string, unknown>[]
}

export function listTemplates(): Promise<TemplateInfo[]> {
  return apiRequest('/templates')
}

export function getTemplate(id: string): Promise<TemplateDetail> {
  return apiRequest(`/templates/${id}`)
}

export function createFromTemplate(templateId: string, params: { name: string; prompt?: string }): Promise<WorkflowSpec> {
  return apiRequest(`/templates/${templateId}/create`, {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

export function saveAsTemplate(workflowId: string, name: string): Promise<TemplateInfo> {
  return apiRequest('/templates/save', {
    method: 'POST',
    body: JSON.stringify({ workflow_id: workflowId, name }),
  })
}

// ==================== Assets ====================

export interface AssetInfo {
  id: string
  execution_id: string
  node_id: string
  task_id: string
  scene_id?: string
  asset_type: string
  file_path: string
  file_size: number
  mime_type: string
  provider: string
  model: string
  source_asset_ids: string[]
  metadata: Record<string, unknown>
  created_at: string
}

export function listAssets(params?: { execution_id?: string; node_id?: string; asset_type?: string }): Promise<AssetInfo[]> {
  const query = new URLSearchParams()
  if (params?.execution_id) query.set('execution_id', params.execution_id)
  if (params?.node_id) query.set('node_id', params.node_id)
  if (params?.asset_type) query.set('asset_type', params.asset_type)
  const qs = query.toString()
  return apiRequest(`/assets${qs ? `?${qs}` : ''}`)
}

export function getAssetLineage(assetId: string): Promise<{ asset_id: string; lineage: AssetInfo[] }> {
  return apiRequest(`/assets/${assetId}/lineage`)
}

export function deleteAsset(assetId: string): Promise<void> {
  return apiRequest(`/assets/${assetId}`, { method: 'DELETE' })
}

export function getAssetDownloadUrl(assetId: string): string {
  return `${API_BASE}/assets/${assetId}/content`
}

// ==================== Config ====================

export interface ProviderInfo {
  name: string
  capabilities: {
    text: boolean
    image: boolean
    video: boolean
  }
}

export interface AppSettings {
  DEFAULT_LLM_PROVIDER: string
  DEFAULT_IMAGE_PROVIDER: string
  DEFAULT_VIDEO_PROVIDER: string
  OLLAMA_API_URL: string
  OLLAMA_MODEL: string
  OPENAI_API_KEY: string
  OPENAI_MODEL: string
  COMFYUI_API_URL: string
  [key: string]: unknown
}

export function getSettings(): Promise<AppSettings> {
  return apiRequest('/config/settings')
}

export function updateSettings(settings: Partial<AppSettings>): Promise<AppSettings> {
  return apiRequest('/config/settings', { method: 'PUT', body: JSON.stringify(settings) })
}

export function listProviders(): Promise<ProviderInfo[]> {
  return apiRequest('/config/providers')
}

export function testProvider(name: string): Promise<{ status: string }> {
  return apiRequest('/config/test-provider', {
    method: 'POST',
    body: JSON.stringify({ provider_name: name }),
  })
}
