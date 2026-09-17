import { useEffect, useState } from 'react'
import { useStudioStore } from '../store'

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
  return (
    <div className="toast-container">
      <div className={`toast toast--error ${exiting ? 'toast--exit' : ''}`}>
        {error}
      </div>
    </div>
  )
}
