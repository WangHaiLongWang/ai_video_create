import { useEffect } from 'react'
import { ReactFlowProvider } from '@xyflow/react'
import { Canvas } from './components/Canvas'
import { NodePalette } from './components/NodePalette'
import { PropertyPanel } from './components/PropertyPanel'
import { TopBar } from './components/TopBar'
import { useStudioStore } from './store'

function KeyboardShortcuts() {
  const undo = useStudioStore((s) => s.undo)
  const redo = useStudioStore((s) => s.redo)

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
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [undo, redo])

  return null
}

export default function App() {
  return (
    <ReactFlowProvider>
      <KeyboardShortcuts />
      <div className="app-shell">
        <TopBar />
        <NodePalette />
        <Canvas />
        <PropertyPanel />
      </div>
    </ReactFlowProvider>
  )
}
