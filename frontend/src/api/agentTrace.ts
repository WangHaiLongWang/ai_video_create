/**
 * Agent Trace API client — read-only trace list/detail (pinned contract).
 *
 * GET /api/agent/traces?workflow_id&kind&limit&offset -> { traces, total }
 * GET /api/agent/traces/{trace_id} -> TraceDetail
 * 404 -> { error: { code: "TRACE_NOT_FOUND", message: str } }
 */

const API_BASE = '/api'

// ---------------------------------------------------------------------------
// Types (match backend contract exactly — snake_case field names)
// ---------------------------------------------------------------------------

export type AgentTraceKind = 'generate' | 'modify' | 'apply'
export type AgentTraceStatus = 'ok' | 'error'
export type AgentTraceStepKind =
  | 'parse'
  | 'intent'
  | 'fallback'
  | 'tool'
  | 'repair'
  | 'compile'
  | 'validate'
export type AgentTraceStepStatus = 'ok' | 'error' | 'skipped'

export interface AgentTraceSummary {
  trace_id: string
  workflow_id: string | null
  kind: AgentTraceKind
  status: AgentTraceStatus
  error_code: string | null
  prompt_hash: string
  provider: string | null
  model: string | null
  repair_count: number
  step_count: number
  duration_ms: number
  created_at: string
}

export interface AgentTraceStep {
  step_id: string
  seq: number
  kind: AgentTraceStepKind
  name: string
  status: AgentTraceStepStatus
  duration_ms: number
  detail: Record<string, unknown>
}

export interface AgentTraceModuleDiffSummary {
  added: number
  removed: number
  updated: number
  modules: Array<Record<string, unknown>>
}

export interface AgentTraceTokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface AgentTraceDetail extends AgentTraceSummary {
  steps: AgentTraceStep[]
  module_diff_summary: AgentTraceModuleDiffSummary | null
  token_usage: AgentTraceTokenUsage | null
}

export interface ListAgentTracesParams {
  workflow_id?: string
  kind?: AgentTraceKind
  limit?: number
  offset?: number
}

export interface ListAgentTracesResponse {
  traces: AgentTraceSummary[]
  total: number
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export class AgentTraceApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    /** Machine-readable code when the API returned one (e.g. "TRACE_NOT_FOUND"). */
    public readonly code?: string,
  ) {
    super(message)
    this.name = 'AgentTraceApiError'
  }
}

/** Shape of the pinned error body: { error: { code, message } } (plus detail fallback). */
interface ErrorBody {
  error?: { code?: string; message?: string }
  detail?: string | { code?: string; message?: string }
}

async function parseErrorResponse(res: Response, action: string): Promise<AgentTraceApiError> {
  let message = `${action}: ${res.status}`
  let code: string | undefined
  try {
    const payload = await res.json() as ErrorBody
    if (payload.error && typeof payload.error === 'object') {
      code = payload.error.code
      if (payload.error.message) {
        message = payload.error.message
      } else if (code) {
        message = `${action}: ${code}`
      }
    } else if (typeof payload.detail === 'string') {
      message = payload.detail
    } else if (payload.detail && typeof payload.detail === 'object') {
      code = payload.detail.code
      if (payload.detail.message) {
        message = payload.detail.message
      } else if (code) {
        message = `${action}: ${code}`
      }
    }
  } catch {
    // Keep the status-based fallback for non-JSON responses.
  }
  return new AgentTraceApiError(message, res.status, code)
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export async function listAgentTraces(
  params?: ListAgentTracesParams,
): Promise<ListAgentTracesResponse> {
  const search = new URLSearchParams()
  if (params?.workflow_id) search.set('workflow_id', params.workflow_id)
  if (params?.kind) search.set('kind', params.kind)
  if (params?.limit !== undefined) search.set('limit', String(params.limit))
  if (params?.offset !== undefined) search.set('offset', String(params.offset))
  const qs = search.toString()
  const res = await fetch(`${API_BASE}/agent/traces${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw await parseErrorResponse(res, 'Failed to list agent traces')
  return res.json() as Promise<ListAgentTracesResponse>
}

export async function getAgentTrace(traceId: string): Promise<AgentTraceDetail> {
  const res = await fetch(`${API_BASE}/agent/traces/${encodeURIComponent(traceId)}`)
  if (!res.ok) throw await parseErrorResponse(res, 'Failed to get agent trace')
  return res.json() as Promise<AgentTraceDetail>
}
