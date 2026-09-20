/**
 * TaskPreview — 展示单个任务的预览信息
 *
 * 显示缩略图/首帧、状态徽标、错误信息、变体标签和重试按钮。
 * 可嵌入 ExecutionPanel 的任务行展开区域。
 */

import { useState, useCallback } from 'react'
import {
  CaretDown,
  CaretRight,
  CheckCircle,
  CircleDashed,
  Lightning,
  Warning,
  XCircle,
  ArrowsClockwise,
  ArrowClockwise,
  Spinner,
} from '@phosphor-icons/react'
import { retryTask } from '../api'
import type { TaskPreview as TaskPreviewType } from '../types'

interface TaskPreviewProps {
  executionId: string
  taskId: string
  status: TaskPreviewType['status']
  firstFrameUrl?: string
  errorMessage?: string
  variantLabel?: string
  progress?: number
  kind?: string
  nodeLabel?: string
  onRetrySuccess?: (taskId: string) => void
}

/** 状态徽标 */
function StatusBadge({ status }: { status: TaskPreviewType['status'] }) {
  switch (status) {
    case 'completed':
      return (
        <span className="task-preview__badge task-preview__badge--completed">
          <CheckCircle size={10} weight="fill" />
          完成
        </span>
      )
    case 'running':
      return (
        <span className="task-preview__badge task-preview__badge--running">
          <Lightning size={10} weight="fill" />
          运行中
        </span>
      )
    case 'failed':
      return (
        <span className="task-preview__badge task-preview__badge--failed">
          <XCircle size={10} weight="fill" />
          失败
        </span>
      )
    case 'pending':
      return (
        <span className="task-preview__badge task-preview__badge--pending">
          <CircleDashed size={10} />
          等待中
        </span>
      )
    default:
      return (
        <span className="task-preview__badge">
          <CircleDashed size={10} />
          {status}
        </span>
      )
  }
}

export function TaskPreview({
  executionId,
  taskId,
  status,
  firstFrameUrl,
  errorMessage,
  variantLabel,
  progress,
  kind,
  nodeLabel,
  onRetrySuccess,
}: TaskPreviewProps) {
  const [retrying, setRetrying] = useState(false)
  const [retryError, setRetryError] = useState<string | null>(null)

  const handleRetry = useCallback(async () => {
    setRetrying(true)
    setRetryError(null)
    try {
      await retryTask(executionId, taskId)
      onRetrySuccess?.(taskId)
    } catch (err) {
      setRetryError(err instanceof Error ? err.message : '重试失败')
    } finally {
      setRetrying(false)
    }
  }, [executionId, taskId, onRetrySuccess])

  const isFailed = status === 'failed'

  return (
    <div className="task-preview">
      {/* 缩略图区域 */}
      <div className="task-preview__media">
        {firstFrameUrl ? (
          <img
            className="task-preview__thumbnail"
            src={firstFrameUrl}
            alt={nodeLabel || taskId}
            loading="lazy"
          />
        ) : (
          <div className="task-preview__placeholder">
            <CircleDashed size={24} className="task-preview__placeholder-icon" />
            <span>{kind || '无预览'}</span>
          </div>
        )}
        {/* 进度覆盖层 */}
        {status === 'running' && progress != null && progress > 0 && (
          <div className="task-preview__progress-bar">
            <div
              className="task-preview__progress-fill"
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
        )}
      </div>

      {/* 信息区域 */}
      <div className="task-preview__info">
        <div className="task-preview__header">
          <StatusBadge status={status} />
          {variantLabel && (
            <span className="task-preview__variant">{variantLabel}</span>
          )}
        </div>

        {nodeLabel && (
          <div className="task-preview__node-label">{nodeLabel}</div>
        )}

        {/* 错误信息 */}
        {isFailed && errorMessage && (
          <div className="task-preview__error">
            <Warning size={12} />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* 重试错误 */}
        {retryError && (
          <div className="task-preview__retry-error">
            <XCircle size={12} />
            <span>{retryError}</span>
          </div>
        )}

        {/* 重试按钮 */}
        {isFailed && (
          <button
            className="task-preview__retry-btn"
            onClick={handleRetry}
            disabled={retrying}
            title="重试此任务"
          >
            {retrying ? (
              <>
                <Spinner size={12} className="task-preview__spinner" />
                重试中...
              </>
            ) : (
              <>
                <ArrowsClockwise size={12} />
                重试任务
              </>
            )}
          </button>
        )}
      </div>
    </div>
  )
}

/** 可展开的任务行，包含预览 */
export function ExpandableTaskRow({
  executionId,
  task,
  onRetrySuccess,
}: {
  executionId: string
  task: TaskPreviewType
  onRetrySuccess?: (taskId: string) => void
}) {
  const [expanded, setExpanded] = useState(false)

  const statusIcon = (() => {
    switch (task.status) {
      case 'completed':
        return <CheckCircle size={14} weight="fill" className="exec-icon exec-icon--completed" />
      case 'running':
        return <Lightning size={14} weight="fill" className="exec-icon exec-icon--running" />
      case 'failed':
        return <XCircle size={14} weight="fill" className="exec-icon exec-icon--failed" />
      default:
        return <CircleDashed size={14} className="exec-icon exec-icon--idle" />
    }
  })()

  return (
    <div className={`task-row task-row--${task.status}`}>
      <div className="task-row__main" onClick={() => setExpanded((e) => !e)}>
        {expanded ? <CaretDown size={12} /> : <CaretRight size={12} />}
        {statusIcon}
        <span className="task-row__label">{task.nodeLabel || task.taskId}</span>
        {task.variantLabel && (
          <span className="task-row__variant">{task.variantLabel}</span>
        )}
        {task.status === 'failed' && (
          <button
            className="exec-retry-btn"
            onClick={(e) => {
              e.stopPropagation()
              // Direct retry without expanding
              retryTask(executionId, task.taskId)
                .then(() => onRetrySuccess?.(task.taskId))
                .catch(() => {})
            }}
            title="快速重试"
          >
            <ArrowsClockwise size={12} />
          </button>
        )}
      </div>
      {expanded && (
        <TaskPreview
          executionId={executionId}
          taskId={task.taskId}
          status={task.status}
          firstFrameUrl={task.firstFrameUrl}
          errorMessage={task.errorMessage}
          variantLabel={task.variantLabel}
          progress={task.progress}
          kind={task.kind}
          nodeLabel={task.nodeLabel}
          onRetrySuccess={onRetrySuccess}
        />
      )}
    </div>
  )
}
