/**
 * AgentTracePanel — Agent 执行轨迹查看器（只读）
 *
 * 列表 + 过滤（kind / workflow_id）+ 步骤时间线详情。
 * 样式与 ExecutionPanel 一致（exec-* 状态徽章 / 事件行）。
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowsClockwise,
  CaretDown,
  CaretRight,
  CheckCircle,
  Clock,
  Warning,
  X,
  XCircle,
} from '@phosphor-icons/react'
import {
  getAgentTrace,
  listAgentTraces,
  type AgentTraceDetail,
  type AgentTraceKind,
  type AgentTraceStep,
  type AgentTraceSummary,
} from '../api/agentTrace'

// ==================== 工具函数 ====================

/** 格式化耗时 (毫秒 → 人类可读) */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainSeconds = seconds % 60
  return `${minutes}:${String(remainSeconds).padStart(2, '0')}`
}

/** 格式化时间戳为 HH:MM:SS */
function formatTimestamp(ts: string): string {
  try {
    const date = new Date(ts)
    return date.toLocaleTimeString('zh-CN', { hour12: false })
  } catch {
    return ts
  }
}

/**
 * prompt_hash 截断显示：前 12 字符 + 省略号。
 * 它是 SHA-256 哈希，不是用户文本 —— 全文绝不渲染到 DOM。
 */
export function truncatePromptHash(hash: string): string {
  if (!hash) return ''
  return hash.length <= 12 ? hash : `${hash.slice(0, 12)}…`
}

/** 疑似密钥的字段名 */
const SECRET_KEY_RE =
  /^(api[_-]?key|apikey|token|access[_-]?key|secret|password|authorization|private[_-]?key|credential)$/i

/** 疑似密钥的字面量（sk-... 形式） */
const SECRET_VALUE_RE = /\bsk-[A-Za-z0-9_-]{6,}/g

/**
 * 递归脱敏 detail：后端已掩码；前端再兜底一层，
 * 任何 sk-... 字面量或密钥字段值都不以原文渲染。
 */
export function maskSecrets(value: unknown, key?: string): unknown {
  if (key && SECRET_KEY_RE.test(key)) return '[REDACTED]'
  if (typeof value === 'string') return value.replace(SECRET_VALUE_RE, '[REDACTED]')
  if (Array.isArray(value)) return value.map((item) => maskSecrets(item))
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = maskSecrets(v, k)
    }
    return out
  }
  return value
}

/** 步骤状态图标 */
function StepStatusIcon({ status }: { status: AgentTraceStep['status'] }) {
  switch (status) {
    case 'ok':
      return <CheckCircle size={14} weight="fill" className="exec-icon exec-icon--completed" />
    case 'error':
      return <XCircle size={14} weight="fill" className="exec-icon exec-icon--failed" />
    default:
      return <Clock size={14} className="exec-icon exec-icon--waiting" />
  }
}

// ==================== 子组件 ====================

/** 单条步骤（可展开 detail） */
function StepRow({
  step,
  expanded,
  onToggle,
}: {
  step: AgentTraceStep
  expanded: boolean
  onToggle: () => void
}) {
  const maskedDetail = useMemo(() => maskSecrets(step.detail), [step.detail])
  const detailJson = useMemo(() => {
    try {
      return JSON.stringify(maskedDetail, null, 2)
    } catch {
      return String(maskedDetail)
    }
  }, [maskedDetail])

  return (
    <div className="agent-trace-step">
      <button
        type="button"
        className={`agent-trace-step-row agent-trace-step-row--${step.status}`}
        onClick={onToggle}
        aria-expanded={expanded}
      >
        {expanded ? <CaretDown size={12} /> : <CaretRight size={12} />}
        <StepStatusIcon status={step.status} />
        <span className="agent-trace-step-seq">#{step.seq}</span>
        <span className="agent-trace-step-kind">{step.kind}</span>
        <span className="agent-trace-step-name">{step.name}</span>
        <span className="exec-node-duration">{formatDuration(step.duration_ms)}</span>
      </button>
      {expanded && (
        <pre className="agent-trace-step-detail" data-testid="step-detail">
          {detailJson}
        </pre>
      )}
    </div>
  )
}

// ==================== 主组件 ====================

export interface AgentTracePanelProps {
  onClose?: () => void
}

export function AgentTracePanel({ onClose }: AgentTracePanelProps) {
  const [traces, setTraces] = useState<AgentTraceSummary[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [listError, setListError] = useState<{ message: string; code?: string } | null>(null)

  const [kindFilter, setKindFilter] = useState<AgentTraceKind | ''>('')
  const [workflowFilter, setWorkflowFilter] = useState('')

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<AgentTraceDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<{ message: string; code?: string } | null>(null)
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set())

  const loadTraces = useCallback(async () => {
    setLoading(true)
    setListError(null)
    try {
      const params: { kind?: AgentTraceKind; workflow_id?: string } = {}
      if (kindFilter) params.kind = kindFilter
      if (workflowFilter.trim()) params.workflow_id = workflowFilter.trim()
      const result = await listAgentTraces(params)
      setTraces(result.traces)
      setTotal(result.total)
    } catch (err) {
      const message = err instanceof Error ? err.message : '加载轨迹列表失败'
      const code = (err as { code?: string }).code
      setListError({ message, code })
      setTraces([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [kindFilter, workflowFilter])

  useEffect(() => {
    void loadTraces()
  }, [loadTraces])

  const handleSelect = useCallback(async (traceId: string) => {
    if (selectedId === traceId) {
      setSelectedId(null)
      setDetail(null)
      setDetailError(null)
      setExpandedSteps(new Set())
      return
    }
    setSelectedId(traceId)
    setDetail(null)
    setDetailError(null)
    setExpandedSteps(new Set())
    setDetailLoading(true)
    try {
      const result = await getAgentTrace(traceId)
      setDetail(result)
    } catch (err) {
      const message = err instanceof Error ? err.message : '加载轨迹详情失败'
      const code = (err as { code?: string }).code
      setDetailError({ message, code })
    } finally {
      setDetailLoading(false)
    }
  }, [selectedId])

  const handleToggleStep = useCallback((stepId: string) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev)
      if (next.has(stepId)) next.delete(stepId)
      else next.add(stepId)
      return next
    })
  }, [])

  /** 步骤按 seq 升序（不依赖后端顺序） */
  const sortedSteps = useMemo(() => {
    if (!detail?.steps) return []
    return [...detail.steps].sort((a, b) => a.seq - b.seq)
  }, [detail])

  return (
    <div className="asset-panel-overlay" onClick={onClose}>
      <div
        className="asset-panel agent-trace-panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Agent 执行轨迹"
      >
        {/* 头部 */}
        <div className="asset-panel-header">
          <div className="asset-panel-title">
            <Clock size={16} weight="fill" />
            Agent 执行轨迹
          </div>
          <button
            type="button"
            className="exec-reset-btn"
            onClick={() => void loadTraces()}
            title="刷新"
            aria-label="刷新"
          >
            <ArrowsClockwise size={12} />
          </button>
          {onClose && (
            <button type="button" className="asset-panel-close" onClick={onClose} aria-label="关闭">
              <X size={18} />
            </button>
          )}
        </div>

        {/* 过滤 */}
        <div className="agent-trace-filters">
          <label className="agent-trace-filter">
            <span>类型</span>
            <select
              aria-label="类型"
              value={kindFilter}
              onChange={(e) => setKindFilter(e.target.value as AgentTraceKind | '')}
            >
              <option value="">全部</option>
              <option value="generate">generate</option>
              <option value="modify">modify</option>
              <option value="apply">apply</option>
            </select>
          </label>
          <label className="agent-trace-filter">
            <span>工作流 ID</span>
            <input
              type="text"
              aria-label="工作流 ID"
              placeholder="wf-..."
              value={workflowFilter}
              onChange={(e) => setWorkflowFilter(e.target.value)}
            />
          </label>
          <span className="agent-trace-total">共 {total} 条</span>
        </div>

        {/* 内容 */}
        <div className="asset-panel-body agent-trace-body">
          {loading && traces.length === 0 && (
            <div className="asset-panel-empty">
              <p>加载中...</p>
            </div>
          )}

          {listError && (
            <div className="agent-error" role="alert">
              <Warning size={14} />
              <span>
                {listError.code ? `[${listError.code}] ` : ''}
                {listError.message}
              </span>
            </div>
          )}

          {!loading && !listError && traces.length === 0 && (
            <div className="asset-panel-empty">
              <strong>暂无轨迹记录</strong>
              <p>Agent 生成 / 修改 / 应用操作会在这里留下执行轨迹</p>
            </div>
          )}

          {traces.length > 0 && (
            <div className="agent-trace-list" role="list">
              {traces.map((trace) => (
                <div key={trace.trace_id} className="agent-trace-group" role="listitem">
                  <button
                    type="button"
                    className={`agent-trace-row agent-trace-row--${trace.status} ${
                      selectedId === trace.trace_id ? 'is-selected' : ''
                    }`}
                    onClick={() => void handleSelect(trace.trace_id)}
                    aria-label={`轨迹 ${trace.trace_id}`}
                  >
                    <span
                      className={`exec-status-badge exec-status-badge--${
                        trace.status === 'ok' ? 'completed' : 'failed'
                      }`}
                    >
                      {trace.status}
                    </span>
                    <span className="exec-event-time">{formatTimestamp(trace.created_at)}</span>
                    <span className="agent-trace-kind">{trace.kind}</span>
                    <span className="agent-trace-provider">
                      {trace.provider ?? '—'}
                      {trace.model ? `/${trace.model}` : ''}
                    </span>
                    <span className="agent-trace-hash" title="Prompt 哈希（SHA-256，非用户文本）">
                      hash {truncatePromptHash(trace.prompt_hash)}
                    </span>
                    <span className="agent-trace-meta">
                      修复 {trace.repair_count} · {trace.step_count} 步 ·{' '}
                      {formatDuration(trace.duration_ms)}
                    </span>
                  </button>

                  {/* 详情：步骤时间线 */}
                  {selectedId === trace.trace_id && (
                    <div className="agent-trace-detail">
                      {detailLoading && (
                        <div className="exec-task-previews-loading">加载中...</div>
                      )}

                      {detailError && (
                        <div className="agent-error" role="alert">
                          <Warning size={14} />
                          <span>
                            {detailError.code ? `[${detailError.code}] ` : ''}
                            {detailError.message}
                          </span>
                        </div>
                      )}

                      {detail && (
                        <>
                          <div className="agent-trace-detail-meta">
                            <span>
                              Prompt 哈希:{' '}
                              <code className="agent-trace-hash">
                                {truncatePromptHash(detail.prompt_hash)}
                              </code>
                            </span>
                            {detail.error_code && (
                              <span className="exec-summary-fail">错误码: {detail.error_code}</span>
                            )}
                            {detail.workflow_id && (
                              <span>工作流: {detail.workflow_id}</span>
                            )}
                          </div>

                          {sortedSteps.length > 0 ? (
                            <div className="exec-events">
                              <div className="exec-events-header">步骤时间线</div>
                              <div className="exec-events-list">
                                {sortedSteps.map((step) => (
                                  <StepRow
                                    key={step.step_id}
                                    step={step}
                                    expanded={expandedSteps.has(step.step_id)}
                                    onToggle={() => handleToggleStep(step.step_id)}
                                  />
                                ))}
                              </div>
                            </div>
                          ) : (
                            <div className="exec-task-previews-empty">无步骤数据</div>
                          )}

                          {detail.module_diff_summary && (
                            <div className="agent-trace-section" data-testid="module-diff-summary">
                              <div className="exec-events-header">模块变更</div>
                              <div className="agent-trace-diff">
                                <span className="exec-summary-ok">
                                  +{detail.module_diff_summary.added}
                                </span>
                                <span className="exec-summary-fail">
                                  -{detail.module_diff_summary.removed}
                                </span>
                                <span className="exec-summary-run">
                                  ~{detail.module_diff_summary.updated}
                                </span>
                                {Array.isArray(detail.module_diff_summary.modules) &&
                                  detail.module_diff_summary.modules.length > 0 && (
                                    <span className="agent-trace-diff-modules">
                                      {detail.module_diff_summary.modules
                                        .map((m) => {
                                          const masked = maskSecrets(m) as Record<string, unknown>
                                          return (
                                            (masked.id as string) ??
                                            (masked.module_id as string) ??
                                            (masked.name as string) ??
                                            JSON.stringify(masked)
                                          )
                                        })
                                        .join(', ')}
                                    </span>
                                  )}
                              </div>
                            </div>
                          )}

                          {detail.token_usage && (
                            <div className="agent-trace-section" data-testid="token-usage">
                              <div className="exec-events-header">Token 用量</div>
                              <div className="agent-trace-tokens">
                                <span>prompt {detail.token_usage.prompt_tokens}</span>
                                <span>completion {detail.token_usage.completion_tokens}</span>
                                <span>total {detail.token_usage.total_tokens}</span>
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
