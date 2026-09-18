import { useEffect, useState } from 'react'
import { useStudioStore } from '../store'

/** Human-readable error code labels */
const ERROR_CODE_LABELS: Record<string, string> = {
  TYPE_MISMATCH: '类型不匹配',
  CARDINALITY_VIOLATION: '端口已满',
  SELF_LOOP: '自环',
  DUPLICATE_EDGE: '重复连接',
  DIRECTION: '方向错误',
}

export function Toast() {
  const error = useStudioStore(s => s.connectionError)
  const setConnectionError = useStudioStore(s => s.setConnectionError)
  const [visible, setVisible] = useState(false)
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    if (error) {
      setVisible(true)
      setExiting(false)
      const timer = setTimeout(() => {
        setExiting(true)
        setTimeout(() => { setVisible(false); setConnectionError(null) }, 200)
      }, 3000)
      return () => clearTimeout(timer)
    }
  }, [error, setConnectionError])

  if (!visible || !error) return null

  // Try to extract error code from message for badge display
  const code = Object.keys(ERROR_CODE_LABELS).find(k => error.includes(k))

  return (
    <div className="toast-container" role="alert" aria-live="assertive">
      <div className={`toast toast--error ${exiting ? 'toast--exit' : ''}`}>
        {code && (
          <span className="toast-error-code">
            {ERROR_CODE_LABELS[code] ?? code}
          </span>
        )}
        <span className="toast-error-msg">{error}</span>
      </div>
    </div>
  )
}
