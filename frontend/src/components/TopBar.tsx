import { CaretDown, FloppyDisk, GearSix, Pause, Play, SquaresFour } from '@phosphor-icons/react'
import { useStudioStore } from '../store'

export function TopBar() {
  const { workflow, isRunning, runMock, stopRun } = useStudioStore()
  return (
    <header className="topbar">
      <div className="brand-mark"><SquaresFour size={19} weight="fill" /></div>
      <div className="title-group">
        <strong>ai_video_create</strong>
        <span>/</span>
        <button>{workflow.name}<CaretDown size={12} /></button>
      </div>
      <div className="top-actions">
        <button className="icon-button" aria-label="设置"><GearSix size={18} /></button>
        <button className="secondary-button"><FloppyDisk size={17} />已自动保存</button>
        {isRunning ? (
          <button className="stop-button" onClick={stopRun}><Pause size={17} weight="fill" />停止</button>
        ) : (
          <button className="run-button" onClick={runMock}><Play size={17} weight="fill" />运行工作流</button>
        )}
      </div>
    </header>
  )
}
