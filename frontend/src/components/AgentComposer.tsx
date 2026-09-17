import { useState } from 'react'
import { Robot, Sparkle, Warning, CheckCircle, Plus, Minus, Pencil, ArrowRight } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import * as api from '../api'

const NODE_KIND_LABELS: Record<string, string> = {
  textInput: '主题输入', storyboard: '分镜生成', textToImage: '文生图',
  imageToVideo: '图生视频', videoConcat: '视频合成', output: '成片输出',
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s}s`
}

function IntentPreview({ intent }: { intent: api.AgentPreviewResponse['intent'] }) {
  if (!intent) return null
  return (
    <div className="agent-preview-section">
      <div className="agent-preview-title">
        <span className="agent-preview-icon"><Plus size={12} weight="bold" /></span>
        工作流结构
      </div>
      <div className="agent-intent-nodes">
        {intent.nodes.map((n, i) => (
          <span key={n.alias} className="agent-intent-node">
            {i > 0 && <ArrowRight size={10} className="agent-intent-arrow" />}
            <span className="agent-intent-kind">{NODE_KIND_LABELS[n.kind] ?? n.kind}</span>
            <span className="agent-intent-alias">{n.alias}</span>
          </span>
        ))}
      </div>
      {intent.connections.length > 0 && (
        <div className="agent-intent-conns">
          {intent.connections.map((c, i) => (
            <div key={i} className="agent-intent-conn">
              <span>{c.source.node}.{c.source.port}</span>
              <ArrowRight size={10} />
              <span>{c.target.node}.{c.target.port}</span>
              {c.mode !== 'direct' && <span className="agent-intent-mode">{c.mode}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function CostPreview({ cost }: { cost: api.AgentPreviewResponse['cost_estimate'] }) {
  if (!cost) return null
  return (
    <div className="agent-preview-section">
      <div className="agent-preview-title">
        <span className="agent-preview-icon"><Sparkle size={12} weight="fill" /></span>
        调用预估
      </div>
      <div className="agent-cost-grid">
        <div className="agent-cost-item">
          <span className="agent-cost-value">{cost.scene_count}</span>
          <span className="agent-cost-label">场景</span>
        </div>
        <div className="agent-cost-item">
          <span className="agent-cost-value">{cost.image_calls}</span>
          <span className="agent-cost-label">图片</span>
        </div>
        <div className="agent-cost-item">
          <span className="agent-cost-value">{cost.video_calls}</span>
          <span className="agent-cost-label">视频</span>
        </div>
        <div className="agent-cost-item">
          <span className="agent-cost-value">{cost.total_calls}</span>
          <span className="agent-cost-label">总调用</span>
        </div>
        <div className="agent-cost-item">
          <span className="agent-cost-value">{formatDuration(cost.estimated_duration_seconds)}</span>
          <span className="agent-cost-label">预计时长</span>
        </div>
      </div>
    </div>
  )
}

function RepairPreview({ steps }: { steps: api.AgentPreviewResponse['repair_steps'] }) {
  if (!steps || steps.length === 0) return null
  return (
    <div className="agent-preview-section">
      <div className="agent-preview-title">
        <span className="agent-preview-icon"><Pencil size={12} /></span>
        自动修复
      </div>
      {steps.map((step, i) => (
        <div key={i} className="agent-repair-step">
          <span className="agent-repair-badge">#{step.attempt}</span>
          {step.repairs_applied.map((r, j) => (
            <span key={j} className="agent-repair-item">{r}</span>
          ))}
        </div>
      ))}
    </div>
  )
}

function PatchPreview({ patch }: { patch: api.GraphPatch }) {
  return (
    <div className="agent-preview-section">
      <div className="agent-preview-title">
        <span className="agent-preview-icon"><Pencil size={12} /></span>
        变更内容
      </div>
      <div className="agent-patch-list">
        {patch.add_nodes.map((n, i) => (
          <div key={i} className="agent-patch-item agent-patch-add">
            <Plus size={11} /> 添加节点 <strong>{(n as Record<string, unknown>).label as string ?? (n as Record<string, unknown>).kind as string}</strong>
          </div>
        ))}
        {patch.remove_nodes.map((id, i) => (
          <div key={i} className="agent-patch-item agent-patch-remove">
            <Minus size={11} /> 删除节点 <code>{id}</code>
          </div>
        ))}
        {patch.update_nodes.map((n, i) => (
          <div key={i} className="agent-patch-item agent-patch-modify">
            <Pencil size={11} /> 修改节点 <code>{(n as Record<string, unknown>).id as string}</code>
          </div>
        ))}
        {patch.add_edges.map((e, i) => (
          <div key={i} className="agent-patch-item agent-patch-add">
            <Plus size={11} /> 添加连线 <code>{(e as Record<string, unknown>).source as string} → {(e as Record<string, unknown>).target as string}</code>
          </div>
        ))}
        {patch.remove_edges.map((id, i) => (
          <div key={i} className="agent-patch-item agent-patch-remove">
            <Minus size={11} /> 删除连线 <code>{id}</code>
          </div>
        ))}
      </div>
    </div>
  )
}

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
        const result = await api.agentApplyPatch(
          workflow.id,
          preview.patch,
          serverVersion ?? undefined,
        )
        setWorkflow(result)
      } else {
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

  const hasV2 = preview?.intent || preview?.cost_estimate
  const hasErrors = (preview?.validation_errors?.length ?? 0) > 0
  const canApply = preview?.can_apply ?? (preview?.spec != null)

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

      {error && (
        <div className="agent-error">
          <Warning size={13} /> {error}
        </div>
      )}

      {preview && (
        <div className="agent-preview">
          {/* Warnings */}
          {preview.warnings.length > 0 && (
            <div className="agent-preview-warnings">
              {preview.warnings.map((w, i) => (
                <div key={i} className="agent-preview-warning">
                  <Warning size={12} /> {w}
                </div>
              ))}
            </div>
          )}

          {/* Validation errors */}
          {hasErrors && (
            <div className="agent-preview-errors">
              {preview.validation_errors!.map((e, i) => (
                <div key={i} className="agent-preview-error">
                  <Warning size={12} /> <code>{e.code}</code> {e.message}
                </div>
              ))}
            </div>
          )}

          {/* Intent structure (v2) */}
          <IntentPreview intent={preview.intent} />

          {/* Patch (modify mode) */}
          {preview.patch && <PatchPreview patch={preview.patch} />}

          {/* Repair steps */}
          <RepairPreview steps={preview.repair_steps} />

          {/* Cost estimate (v2) */}
          <CostPreview cost={preview.cost_estimate} />

          {/* Diff text (legacy) */}
          {preview.diff && !hasV2 && (
            <div className="agent-preview-diff">
              <pre>{preview.diff}</pre>
            </div>
          )}

          {/* Destructive warning */}
          {preview.destructive && (
            <div className="agent-destructive-warning">
              <Warning size={13} weight="fill" /> 此操作将删除节点或连线
            </div>
          )}

          {/* Actions */}
          <div className="agent-preview-actions">
            <button
              className={`agent-apply-btn ${!canApply ? 'disabled' : ''}`}
              onClick={handleApply}
              disabled={!canApply}
            >
              <CheckCircle size={14} /> {canApply ? '应用' : '无法应用'}
            </button>
            <button className="agent-cancel-btn" onClick={handleCancel}>取消</button>
          </div>
        </div>
      )}
    </section>
  )
}
