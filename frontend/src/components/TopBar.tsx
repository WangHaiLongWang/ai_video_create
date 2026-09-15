import { useState } from 'react'
import { CaretDown, FloppyDisk, GearSix, Pause, Play, SquaresFour, TreeStructure } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import SettingsPanel from './SettingsPanel'
import TemplateSelector from './TemplateSelector'

export function TopBar() {
  const { workflow, isRunning, runExecution, stopRun, runMessage, execution, setWorkflow } = useStudioStore()
  const [showSettings, setShowSettings] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)

  const handleTemplateSelect = (templateId: string) => {
    // TemplateSelector 内部已处理创建，这里刷新工作流
    setShowTemplates(false)
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
          <button className="icon-button" onClick={() => setShowTemplates(true)} aria-label="模板">
            <TreeStructure size={18} />
          </button>
          <button className="icon-button" onClick={() => setShowSettings(true)} aria-label="设置">
            <GearSix size={18} />
          </button>
          <button className="secondary-button"><FloppyDisk size={17} />已自动保存</button>
          {isRunning ? (
            <button className="stop-button" onClick={stopRun}><Pause size={17} weight="fill" />停止</button>
          ) : (
            <button className="run-button" onClick={runExecution}><Play size={17} weight="fill" />运行工作流</button>
          )}
        </div>
        {isRunning && execution && (
          <div className="execution-status">
            <span>{runMessage}</span>
            <span>{execution.completedCount}/{execution.taskCount} 任务</span>
          </div>
        )}
      </header>

      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}
      {showTemplates && <TemplateSelector onSelect={handleTemplateSelect} onClose={() => setShowTemplates(false)} />}
    </>
  )
}
