import { useEffect } from 'react'
import { ReactFlowProvider } from '@xyflow/react'
import { Canvas } from './components/Canvas'
import { ExecutionPanel } from './components/ExecutionPanel'
import { NodePalette } from './components/NodePalette'
import { PropertyPanel } from './components/PropertyPanel'
import { Toast } from './components/Toast'
import { TopBar } from './components/TopBar'
import { useStudioStore } from './store'

function KeyboardShortcuts() {
  const undo = useStudioStore((s) => s.undo)
  const redo = useStudioStore((s) => s.redo)
  const deleteSelectedEdge = useStudioStore((s) => s.deleteSelectedEdge)
  const selectedEdgeId = useStudioStore((s) => s.selectedEdgeId)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey
      if (mod && e.key === 'z' && !e.shiftKey) {
        e.preventDefault()
        undo()
      } else if (mod && e.key === 'z' && e.shiftKey) {
        e.preventDefault()
        redo()
      } else if (mod && e.key === 'y') {
        e.preventDefault()
        redo()
      } else if ((e.key === 'Delete' || e.key === 'Backspace') && selectedEdgeId) {
        // Don't intercept if user is typing in an input
        const tag = (e.target as HTMLElement)?.tagName
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
        e.preventDefault()
        deleteSelectedEdge()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [undo, redo, deleteSelectedEdge, selectedEdgeId])

  return null
}

export default function App() {
  return (
    <ReactFlowProvider>
      <KeyboardShortcuts />
      <Toast />
      <div className="app-shell">
        <TopBar />
        <NodePalette />
        <Canvas />
        <PropertyPanel />
        <ExecutionPanel />
      </div>
    </ReactFlowProvider>
  )
}
