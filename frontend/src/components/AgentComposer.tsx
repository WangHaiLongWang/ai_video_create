import { useState } from 'react'
import { Robot, Sparkle } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import * as api from '../api'

export function AgentComposer() {
  const [prompt, setPrompt] = useState('创建一个 5 镜头的未来城市短视频流程')
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState<api.AgentPreviewResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(true)

  const { setWorkflow, workflow, serverVersion } = useStudioStore()

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setError(null)

    try {
      const result = await api.agentGeneratePreview(prompt)
      setPreview(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成失败')
    } finally {
      setLoading(false)
    }
  }

  const handleApply = async () => {
    if (!preview?.spec) return

    try {
      if (preview.patch) {
        // 应用修改
        const result = await api.agentApplyPatch(
          workflow.id,
          preview.patch,
          serverVersion ?? undefined,
        )
        setWorkflow(result)
      } else {
        // 新建工作流
        setWorkflow(preview.spec)
      }
      setPreview(null)
      setPrompt('')
    } catch (e) {
      setError(e instanceof Error ? e.message : '应用失败')
    }
  }

  const handleCancel = () => {
    setPreview(null)
    setError(null)
  }

  if (!open) {
    return (
      <button className="agent-fab" onClick={() => setOpen(true)} aria-label="打开 Agent">
        <Robot size={21} />
      </button>
    )
  }

  return (
    <section className="agent-composer">
      <div className="agent-title">
        <Robot size={18} weight="duotone" />
        <strong>Workflow Agent</strong>
        <button onClick={() => setOpen(false)}>收起</button>
      </div>
      <div className="agent-input">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="描述你想要的工作流..."
          rows={3}
          aria-label="描述想要创建的工作流"
        />
        <button onClick={handleGenerate} disabled={loading}>
          <Sparkle size={17} weight="fill" />
          {loading ? '生成中...' : '生成预览'}
        </button>
      </div>

      {error && <div className="error" style={{ color: '#ff6b6b', margin: '8px 0' }}>{error}</div>}

      {preview && (
        <div className="preview" style={{ margin: '12px 0', padding: 12, border: '1px solid #444', borderRadius: 8 }}>
          <h4 style={{ margin: '0 0 8px', fontSize: 14 }}>预览</h4>
          {preview.warnings.length > 0 && (
            <div className="warnings" style={{ marginBottom: 8 }}>
              {preview.warnings.map((w, i) => (
                <div key={i} className="warning" style={{ color: '#ffa94d', fontSize: 13 }}>{w}</div>
              ))}
            </div>
          )}
          {preview.diff && <pre style={{ fontSize: 12, color: '#aaa', whiteSpace: 'pre-wrap' }}>{preview.diff}</pre>}
          {preview.destructive && (
            <div className="destructive-warning" style={{ color: '#ff6b6b', fontWeight: 'bold', margin: '8px 0' }}>
              此操作将删除节点或连线
            </div>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleApply} style={{ flex: 1 }}>
              <Sparkle size={14} weight="fill" /> 应用
            </button>
            <button onClick={handleCancel} style={{ flex: 1 }}>取消</button>
          </div>
        </div>
      )}
    </section>
  )
}
