import { ArrowsClockwise, Check, Sparkle, SquaresFour } from '@phosphor-icons/react'
import { useStudioStore } from '../store'

export function PropertyPanel() {
  const { workflow, selectedNodeId, updateConfig, runMessage, isRunning } = useStudioStore()
  const node = workflow.nodes.find((item) => item.id === selectedNodeId)
  return (
    <aside className="properties">
      <div className="panel-heading"><span>节点配置</span><ArrowsClockwise size={15} /></div>
      {!node ? (
        <div className="empty-panel">
          <SquaresFour size={30} weight="duotone" />
          <strong>选择一个节点</strong>
          <p>在画布中选择节点后，可以在这里调整生成参数。</p>
        </div>
      ) : (
        <div className="property-form">
          <div className="selected-title">
            <span>{node.data.label}</span>
            <small>{node.data.kind}</small>
          </div>
          {Object.entries(node.data.config).map(([key, value]) => (
            <label key={key}>
              <span>{key}</span>
              {typeof value === 'boolean' ? (
                <input type="checkbox" checked={value} onChange={(event) => updateConfig(key, event.target.checked)} />
              ) : (
                <input
                  type={typeof value === 'number' ? 'number' : 'text'}
                  value={String(value)}
                  onChange={(event) => updateConfig(key, typeof value === 'number' ? Number(event.target.value) : event.target.value)}
                />
              )}
            </label>
          ))}
        </div>
      )}
      <div className={`run-summary ${isRunning ? 'is-active' : ''}`}>
        {isRunning ? <Sparkle size={18} weight="fill" /> : <Check size={18} weight="bold" />}
        <div><strong>{isRunning ? 'Mock 执行中' : '运行状态'}</strong><span>{runMessage}</span></div>
      </div>
    </aside>
  )
}
