/**
 * TopBar — 顶部工具栏
 *
 * 使用 executionStore 管理执行操作 (启动/停止)
 * 使用 workflowStore 管理工作流状态
 */

import { useMemo, useState, useCallback } from 'react'
import { CaretDown, Export, FileArrowUp, FloppyDisk, FilmStrip, Folder, GearSix, List, Pause, Play, SquaresFour, TreeStructure } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import { useExecutionStore } from '../stores/executionStore'
import { computeCallEstimate } from '../utils/callEstimate'
import { AssetPanel } from './AssetPanel'
import { ExportDialog } from './ExportDialog'
import { ImportDialog } from './ImportDialog'
import SettingsPanel from './SettingsPanel'
import TemplateSelector from './TemplateSelector'
import WorkflowListPage from './WorkflowListPage'

export function TopBar({ onToggleSceneEditor }: { onToggleSceneEditor?: () => void }) {
  const { workflow, ensureSavedToServer, setWorkflow } = useStudioStore()
  const {
    status: executionStatus,
    socketStatus,
    completedCount,
    taskCount,
    startExecution,
    stopExecution,
  } = useExecutionStore()

  const [showSettings, setShowSettings] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)
  const [showWorkflowList, setShowWorkflowList] = useState(false)
  const [showAssets, setShowAssets] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [showImport, setShowImport] = useState(false)

  const isRunning = executionStatus === 'running'

  // Compute call estimate from current workflow spec
  const callEstimate = useMemo(() => {
    return computeCallEstimate(workflow)
  }, [workflow])

  const handleTemplateSelect = (_templateId: string) => {
    // TemplateSelector 内部已处理创建，这里刷新工作流
    setShowTemplates(false)
  }

  /** 运行工作流: 先确保保存到服务器，再启动执行 */
  const handleRun = useCallback(async () => {
    const saved = await ensureSavedToServer()
    if (!saved) {
      console.error('保存失败，无法执行')
      return
    }
    startExecution(workflow.id)
  }, [ensureSavedToServer, startExecution, workflow.id])

  /** 停止执行 */
  const handleStop = useCallback(() => {
    stopExecution()
  }, [stopExecution])

  /** 获取执行状态提示文本 */
  const getStatusText = (): string => {
    switch (executionStatus) {
      case 'idle': return '准备执行'
      case 'running': return `执行中: ${completedCount}/${taskCount} 任务`
      case 'completed': return '执行完成'
      case 'failed': return '执行失败'
      case 'cancelled': return '执行已取消'
      default: return executionStatus
    }
  }

  return (
    <>
      <header className="topbar">
        <div className="brand-mark"><SquaresFour size={19} weight="fill" /></div>
        <div className="title-group">
          <strong>ai_video_create</strong>
          <span>/</span>
          <button>{workflow.name}<CaretDown size={12} /></button>
        </div>
        <div className="top-actions">
          <button className="icon-button" onClick={() => setShowWorkflowList(true)} aria-label="工作流列表">
            <List size={18} />
          </button>
          <button className="icon-button" onClick={() => setShowAssets(true)} aria-label="资产">
            <Folder size={18} />
          </button>
          <button className="icon-button" onClick={onToggleSceneEditor} aria-label="场景编辑器">
            <FilmStrip size={18} />
          </button>
          <button className="icon-button" onClick={() => setShowTemplates(true)} aria-label="模板">
            <TreeStructure size={18} />
          </button>
          <button className="icon-button" onClick={() => setShowSettings(true)} aria-label="设置">
            <GearSix size={18} />
          </button>
          <button className="icon-button" onClick={() => setShowExport(true)} aria-label="导出">
            <Export size={18} />
          </button>
          <button className="icon-button" onClick={() => setShowImport(true)} aria-label="导入">
            <FileArrowUp size={18} />
          </button>
          <button className="secondary-button"><FloppyDisk size={17} />已自动保存</button>
          {callEstimate.sceneCount > 0 && (
            <span className="call-estimate-badge" title={`场景: ${callEstimate.sceneCount} | 图片: ${callEstimate.imageCalls} | 视频: ${callEstimate.videoCalls}`}>
              {callEstimate.imageCalls} 图 · {callEstimate.videoCalls} 视频 · {callEstimate.sceneCount} 场景
            </span>
          )}
          {isRunning ? (
            <button className="stop-button" onClick={handleStop}><Pause size={17} weight="fill" />停止</button>
          ) : (
            <button className="run-button" onClick={handleRun}><Play size={17} weight="fill" />运行工作流</button>
          )}
        </div>
        {isRunning && (
          <div className="execution-status">
            <span
              className={`ws-indicator ws-${socketStatus}`}
              title={
                socketStatus === 'connected' ? 'WebSocket 已连接' :
                socketStatus === 'connecting' ? 'WebSocket 连接中...' :
                'WebSocket 已断开'
              }
            />
            <span>{getStatusText()}</span>
            {taskCount > 0 && (
              <span>{completedCount}/{taskCount} 任务</span>
            )}
          </div>
        )}
      </header>

      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}
      {showTemplates && <TemplateSelector onSelect={handleTemplateSelect} onClose={() => setShowTemplates(false)} />}
      {showWorkflowList && <WorkflowListPage onClose={() => setShowWorkflowList(false)} />}
      {showAssets && <AssetPanel onClose={() => setShowAssets(false)} />}
      {showExport && <ExportDialog workflowId={workflow.id} onClose={() => setShowExport(false)} />}
      {showImport && (
        <ImportDialog
          workflowId={workflow.id}
          onClose={() => setShowImport(false)}
          onImported={() => { /* parent can refresh if needed */ }}
        />
      )}
    </>
  )
}
