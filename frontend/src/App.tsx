import { useEffect } from 'react'
import { ReactFlowProvider } from '@xyflow/react'
import { Canvas } from './components/Canvas'
import { ExecutionPanel } from './components/ExecutionPanel'
import { NodePalette } from './components/NodePalette'
import { PropertyPanel } from './components/PropertyPanel'
import { Toast } from './components/Toast'
import { TopBar } from './components/TopBar'
import { useStudioStore } from './store'

function isInputFocused() {
  const tag = (document.activeElement as HTMLElement)?.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}

function KeyboardShortcuts() {
  const undo = useStudioStore((s) => s.undo)
  const redo = useStudioStore((s) => s.redo)
  const deleteSelectedEdge = useStudioStore((s) => s.deleteSelectedEdge)
  const deleteSelectedNodes = useStudioStore((s) => s.deleteSelectedNodes)
  const selectedEdgeId = useStudioStore((s) => s.selectedEdgeId)
  const selectedNodeIds = useStudioStore((s) => s.selectedNodeIds)
  const focusedNodeId = useStudioStore((s) => s.focusedNodeId)
  const selectAllNodes = useStudioStore((s) => s.selectAllNodes)
  const copySelectedNodes = useStudioStore((s) => s.copySelectedNodes)
  const pasteNodes = useStudioStore((s) => s.pasteNodes)
  const clearSelection = useStudioStore((s) => s.clearSelection)
  const focusNode = useStudioStore((s) => s.focusNode)
  const selectNode = useStudioStore((s) => s.selectNode)
  const nudgeSelectedNodes = useStudioStore((s) => s.nudgeSelectedNodes)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't intercept when user is typing in an input/textarea/select
      if (isInputFocused()) return

      const mod = e.ctrlKey || e.metaKey

      // Ctrl+Z — undo
      if (mod && e.key === 'z' && !e.shiftKey) {
        e.preventDefault()
        undo()
      // Ctrl+Shift+Z / Ctrl+Y — redo
      } else if ((mod && e.key === 'z' && e.shiftKey) || (mod && e.key === 'y')) {
        e.preventDefault()
        redo()
      // Ctrl+A — select all nodes
      } else if (mod && e.key === 'a') {
        e.preventDefault()
        selectAllNodes()
      // Ctrl+C — copy selected nodes
      } else if (mod && e.key === 'c') {
        e.preventDefault()
        copySelectedNodes()
      // Ctrl+V — paste nodes
      } else if (mod && e.key === 'v') {
        e.preventDefault()
        pasteNodes()
      // Escape — clear selection and focus
      } else if (e.key === 'Escape') {
        e.preventDefault()
        clearSelection()
        focusNode(null)
      // Delete / Backspace — delete selected nodes or edge
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault()
        if (selectedNodeIds.length > 0) {
          deleteSelectedNodes()
        } else if (selectedEdgeId) {
          deleteSelectedEdge()
        }
      // Tab / Shift+Tab — cycle focus between nodes
      } else if (e.key === 'Tab') {
        e.preventDefault()
        const nodes = useStudioStore.getState().workflow.nodes
        if (nodes.length === 0) return
        const currentIdx = focusedNodeId
          ? nodes.findIndex((n) => n.id === focusedNodeId)
          : -1
        const nextIdx = e.shiftKey
          ? (currentIdx <= 0 ? nodes.length - 1 : currentIdx - 1)
          : (currentIdx + 1) % nodes.length
        focusNode(nodes[nextIdx].id)
      // Enter — select focused node (opens property panel)
      } else if (e.key === 'Enter' && focusedNodeId) {
        e.preventDefault()
        selectNode(focusedNodeId)
      // Arrow keys — nudge selected nodes (1px per press)
      } else if (e.key === 'ArrowUp' && selectedNodeIds.length > 0) {
        e.preventDefault()
        nudgeSelectedNodes(0, e.shiftKey ? -10 : -1)
      } else if (e.key === 'ArrowDown' && selectedNodeIds.length > 0) {
        e.preventDefault()
        nudgeSelectedNodes(0, e.shiftKey ? 10 : 1)
      } else if (e.key === 'ArrowLeft' && selectedNodeIds.length > 0) {
        e.preventDefault()
        nudgeSelectedNodes(e.shiftKey ? -10 : -1, 0)
      } else if (e.key === 'ArrowRight' && selectedNodeIds.length > 0) {
        e.preventDefault()
        nudgeSelectedNodes(e.shiftKey ? 10 : 1, 0)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [
    undo, redo, deleteSelectedEdge, deleteSelectedNodes,
    selectedEdgeId, selectedNodeIds, focusedNodeId,
    selectAllNodes, copySelectedNodes, pasteNodes, clearSelection,
    focusNode, selectNode, nudgeSelectedNodes,
  ])

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
