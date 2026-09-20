/**
 * ExecutionPanel — 执行监控面板
 *
 * 显示执行状态、节点进度、事件日志和执行摘要。
 * 支持折叠/展开。支持任务级预览和单项重试。
 */

import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import {
  CaretDown,
  CaretRight,
  CheckCircle,
  CircleDashed,
  Clock,
  ArrowsClockwise,
  Warning,
  XCircle,
  Lightning,
  Eye,
} from '@phosphor-icons/react'
import { useExecutionStore } from '../stores/executionStore'
import type { ExecutionStatus, NodeExecutionState, ExecutionEvent } from '../stores/executionStore'
import { ExpandableTaskRow } from './TaskPreview'
import type { TaskPreview as TaskPreviewType } from '../types'
import * as api from '../api'

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

/** 获取状态对应的图标 */
function StatusIcon({ status }: { status: NodeExecutionState['status'] }) {
  switch (status) {
    case 'completed':
      return <CheckCircle size={16} weight="fill" className="exec-icon exec-icon--completed" />
    case 'running':
      return <Lightning size={16} weight="fill" className="exec-icon exec-icon--running" />
    case 'failed':
      return <XCircle size={16} weight="fill" className="exec-icon exec-icon--failed" />
    case 'waiting':
      return <Clock size={16} className="exec-icon exec-icon--waiting" />
    default:
      return <CircleDashed size={16} className="exec-icon exec-icon--idle" />
  }
}

/** 获取执行状态的文本 */
function statusLabel(status: ExecutionStatus): string {
  switch (status) {
    case 'idle': return '待执行'
    case 'running': return '运行中'
    case 'completed': return '已完成'
    case 'failed': return '执行失败'
    case 'cancelled': return '已取消'
    default: return status
  }
}

/** 获取事件类型对应的描述 */
function eventDescription(event: ExecutionEvent): string {
  const { type, message, node_id } = event
  if (message) return message
  switch (type) {
    case 'execution.started': return '开始执行'
    case 'execution.completed': return '执行完成'
    case 'execution.failed': return '执行失败'
    case 'execution.cancelled': return '执行已取消'
    case 'node.started': return `${node_id} 开始执行`
    case 'node.completed': return `${node_id} 执行完成`
    case 'node.failed': return `${node_id} 执行失败`
    default: return type
  }
}

// ==================== 子组件 ====================

/** 节点执行状态行 */
function NodeStatusRow({
  nodeState,
  onRetry,
  children,
}: {
  nodeState: NodeExecutionState
  onRetry: (nodeId: string) => void
  children?: React.ReactNode
}) {
  const isFailed = nodeState.status === 'failed'
  const isRunning = nodeState.status === 'running'

  return (
    <div className={`exec-node-row exec-node-row--${nodeState.status}`}>
      <StatusIcon status={nodeState.status} />
      <span className="exec-node-label">{nodeState.nodeId}</span>
      {isRunning && nodeState.taskCount > 1 && (
        <span className="exec-node-progress">
          {nodeState.completedCount}/{nodeState.taskCount}
        </span>
      )}
      <span className="exec-node-duration">
        {nodeState.duration ? formatDuration(nodeState.duration) : '等待中'}
      </span>
      {isFailed && (
        <button
          className="exec-retry-btn"
          onClick={() => onRetry(nodeState.nodeId)}
          title="重试此节点"
        >
          <ArrowsClockwise size={12} />
        </button>
      )}
      {children}
    </div>
  )
}

/** 执行事件日志条目 */
function EventLogEntry({ event }: { event: ExecutionEvent }) {
  return (
    <div className={`exec-event exec-event--${event.type.split('.')[0]}`}>
      <span className="exec-event-time">{formatTimestamp(event.timestamp)}</span>
      <span className="exec-event-msg">{eventDescription(event)}</span>
    </div>
  )
}

// ==================== 主组件 ====================

export function ExecutionPanel() {
  const [collapsed, setCollapsed] = useState(false)
  const [expandedNodeId, setExpandedNodeId] = useState<string | null>(null)
  const [taskPreviews, setTaskPreviews] = useState<Map<string, TaskPreviewType[]>>(new Map())
  const [loadingPreview, setLoadingPreview] = useState(false)
  const eventsEndRef = useRef<HTMLDivElement>(null)

  const executionId = useExecutionStore((s) => s.executionId)
  const status = useExecutionStore((s) => s.status)
  const taskCount = useExecutionStore((s) => s.taskCount)
  const completedCount = useExecutionStore((s) => s.completedCount)
  const nodeStates = useExecutionStore((s) => s.nodeStates)
  const events = useExecutionStore((s) => s.events)
  const startTime = useExecutionStore((s) => s.startTime)
  const retryNode = useExecutionStore((s) => s.retryNode)
  const resetExecution = useExecutionStore((s) => s.resetExecution)

  // 自动滚动事件日志到底部
  useEffect(() => {
    if (!collapsed) {
      eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events.length, collapsed])

  const handleToggle = useCallback(() => setCollapsed((c) => !c), [])
  const handleRetry = useCallback((nodeId: string) => retryNode(nodeId), [retryNode])
  const handleReset = useCallback(() => resetExecution(), [resetExecution])

  // 展开/折叠节点预览，展开时加载任务预览数据
  const handleToggleNodePreview = useCallback(async (nodeId: string) => {
    if (expandedNodeId === nodeId) {
      setExpandedNodeId(null)
      return
    }
    setExpandedNodeId(nodeId)

    // 加载该节点的任务预览数据
    if (executionId && !taskPreviews.has(nodeId)) {
      setLoadingPreview(true)
      try {
        const tasks = await api.getExecutionTasks(executionId)
        const nodeTasks = tasks.filter((t) => t.node_id === nodeId)
        const previews: TaskPreviewType[] = nodeTasks.map((t) => ({
          taskId: t.id,
          status: t.status as TaskPreviewType['status'],
          firstFrameUrl: undefined,
          errorMessage: t.error || undefined,
          variantLabel: t.item_key?.includes(':') ? t.item_key.split(':')[1] : t.item_key || undefined,
          progress: t.status === 'completed' ? 100 : t.status === 'running' ? 50 : 0,
          kind: t.kind,
          nodeLabel: t.label,
        }))
        setTaskPreviews((prev) => new Map(prev).set(nodeId, previews))
      } catch (err) {
        console.error('加载任务预览失败:', err)
      } finally {
        setLoadingPreview(false)
      }
    }
  }, [executionId, expandedNodeId, taskPreviews])

  // 重试成功后刷新任务预览数据
  const handleTaskRetrySuccess = useCallback(async (taskId: string) => {
    if (!executionId) return
    try {
      const preview = await api.getTaskPreview(executionId, taskId)
      // 找到包含此任务的节点并更新预览数据
      for (const [nodeId, previews] of taskPreviews.entries()) {
        const idx = previews.findIndex((p) => p.taskId === taskId)
        if (idx >= 0) {
          const updated = [...previews]
          updated[idx] = {
            ...updated[idx],
            status: preview.status as TaskPreviewType['status'],
            errorMessage: preview.error_message || undefined,
          }
          setTaskPreviews((prev) => new Map(prev).set(nodeId, updated))
          break
        }
      }
    } catch (err) {
      console.error('刷新任务预览失败:', err)
    }
  }, [executionId, taskPreviews])

  // 排序后的节点列表
  const sortedNodes = useMemo(() => {
    return Array.from(nodeStates.values()).sort((a, b) => {
      const order = { running: 0, failed: 1, waiting: 2, completed: 3, idle: 4 }
      return (order[a.status] ?? 5) - (order[b.status] ?? 5)
    })
  }, [nodeStates])

  // 统计
  const stats = useMemo(() => {
    let success = 0
    let failed = 0
    let running = 0
    nodeStates.forEach((ns) => {
      if (ns.status === 'completed') success++
      else if (ns.status === 'failed') failed++
      else if (ns.status === 'running') running++
    })
    const elapsed = startTime ? Date.now() - startTime : 0
    return { success, failed, running, elapsed }
  }, [nodeStates, startTime])

  // 如果没有执行记录，不显示面板
  if (!executionId && status === 'idle') {
    return null
  }

  return (
    <div className={`execution-panel ${collapsed ? 'is-collapsed' : ''}`}>
      {/* 头部: 标题 + 折叠按钮 */}
      <div className="exec-header" onClick={handleToggle}>
        <span className="exec-header-title">
          <Lightning size={14} weight="fill" />
          执行监控
        </span>
        <span className="exec-header-status">
          <span className={`exec-status-badge exec-status-badge--${status}`}>
            {statusLabel(status)}
          </span>
          {startTime !== null && startTime > 0 && (
            <span className="exec-elapsed">{formatDuration(stats.elapsed)}</span>
          )}
        </span>
        {collapsed ? <CaretRight size={14} /> : <CaretDown size={14} />}
      </div>

      {!collapsed && (
        <div className="exec-body">
          {/* 摘要信息 */}
          {taskCount > 0 && (
            <div className="exec-summary">
              <span>任务: {completedCount}/{taskCount}</span>
              {stats.success > 0 && <span className="exec-summary-ok">{stats.success} 成功</span>}
              {stats.failed > 0 && <span className="exec-summary-fail">{stats.failed} 失败</span>}
              {stats.running > 0 && <span className="exec-summary-run">{stats.running} 运行中</span>}
            </div>
          )}

          {/* 节点状态列表 */}
          {sortedNodes.length > 0 && (
            <div className="exec-nodes">
              {sortedNodes.map((nodeState) => (
                <div key={nodeState.nodeId} className="exec-node-group">
                  <NodeStatusRow
                    nodeState={nodeState}
                    onRetry={handleRetry}
                  >
                    {(nodeState.taskCount > 1 || nodeState.status === 'failed' || nodeState.status === 'completed') && (
                      <button
                        className="exec-preview-toggle"
                        onClick={() => handleToggleNodePreview(nodeState.nodeId)}
                        title={expandedNodeId === nodeState.nodeId ? '折叠任务预览' : '展开任务预览'}
                      >
                        <Eye size={12} />
                      </button>
                    )}
                  </NodeStatusRow>
                  {/* 展开的任务预览区域 */}
                  {expandedNodeId === nodeState.nodeId && (
                    <div className="exec-task-previews">
                      {loadingPreview && taskPreviews.size === 0 ? (
                        <div className="exec-task-previews-loading">加载中...</div>
                      ) : (
                        (taskPreviews.get(nodeState.nodeId) || []).map((task) => (
                          <ExpandableTaskRow
                            key={task.taskId}
                            executionId={executionId!}
                            task={task}
                            onRetrySuccess={handleTaskRetrySuccess}
                          />
                        ))
                      )}
                      {taskPreviews.get(nodeState.nodeId)?.length === 0 && !loadingPreview && (
                        <div className="exec-task-previews-empty">无任务数据</div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* 事件日志 */}
          {events.length > 0 && (
            <div className="exec-events">
              <div className="exec-events-header">事件日志</div>
              <div className="exec-events-list">
                {events.map((event, i) => (
                  <EventLogEntry key={event.event_id ?? `evt-${i}`} event={event} />
                ))}
                <div ref={eventsEndRef} />
              </div>
            </div>
          )}

          {/* 重置按钮 (执行完成后) */}
          {(status === 'completed' || status === 'failed' || status === 'cancelled') && (
            <div className="exec-actions">
              <button className="exec-reset-btn" onClick={handleReset}>
                清除执行记录
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
