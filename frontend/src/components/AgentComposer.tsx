import { useCallback, useState } from 'react'
import { Robot, Sparkle, Warning, CheckCircle, Pencil, ArrowRight, TreeStructure, Play, ArrowsClockwise, Plus, Minus } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import { useExecutionStore } from '../stores/executionStore'
import * as api from '../api'
import type { AgentPreviewResponse_v2, WorkflowIntent, WorkflowSpec, GraphPatch, ValidationError, RepairStep, CostEstimate } from '../api'
import type { StudioNode, EnhancedEdge } from '../types'

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

/* ==================== Sub-components ==================== */

function IntentPreview({ intent }: { intent: WorkflowIntent }) {
  return (
    <div className="agent-preview-section">
      <div className="agent-preview-title">
        <span className="agent-preview-icon"><TreeStructure size={12} weight="bold" /></span>
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

function CompiledWorkflowPreview({ spec }: { spec: WorkflowSpec }) {
  return (
    <div className="agent-preview-section">
      <div className="agent-preview-title">
        <span className="agent-preview-icon"><TreeStructure size={12} weight="bold" /></span>
        编译后工作流 ({spec.schemaVersion})
      </div>
      <div className="agent-compiled-nodes">
        {spec.nodes.map((node: StudioNode) => (
          <div key={node.id} className="agent-compiled-node">
            <span className="agent-compiled-node-kind">{NODE_KIND_LABELS[node.data.kind] ?? node.data.kind}</span>
            <span className="agent-compiled-node-label">{node.data.label}</span>
            <code className="agent-compiled-node-id">{node.id}</code>
          </div>
        ))}
      </div>
      <div className="agent-compiled-edges">
        {spec.edges.map((edge: EnhancedEdge) => (
          <div key={edge.id} className="agent-compiled-edge">
            <code>{edge.source}</code>
            {edge.sourceHandle && <span className="agent-compiled-handle">.{edge.sourceHandle}</span>}
            <ArrowRight size={10} />
            <code>{edge.target}</code>
            {edge.targetHandle && <span className="agent-compiled-handle">.{edge.targetHandle}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

function CostPreview({ cost }: { cost: CostEstimate }) {
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

function RepairPreview({ steps }: { steps: RepairStep[] }) {
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

function ValidationErrors({ errors }: { errors: ValidationError[] }) {
  if (!errors || errors.length === 0) return null
  return (
    <div className="agent-preview-errors">
      {errors.map((e, i) => (
        <div key={i} className="agent-preview-error">
          <Warning size={12} /> <code>{e.code}</code> {e.message}
        </div>
      ))}
    </div>
  )
}

function Warnings({ warnings }: { warnings: string[] }) {
  if (!warnings || warnings.length === 0) return null
  return (
    <div className="agent-preview-warnings">
      {warnings.map((w, i) => (
        <div key={i} className="agent-preview-warning">
          <Warning size={12} /> {w}
        </div>
      ))}
    </div>
  )
}

function PatchPreview({ patch }: { patch: GraphPatch }) {
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

/* ==================== Main Component ==================== */

export function AgentComposer() {
  const [prompt, setPrompt] = useState('创建一个 5 镜头的未来城市短视频流程')
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState<AgentPreviewResponse_v2 | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(true)
  const [applying, setApplying] = useState(false)

  // v2 flow: undo, run, success
  const [undoSnapshot, setUndoSnapshot] = useState<WorkflowSpec | null>(null)
  const [applied, setApplied] = useState(false)
  const [canRun, setCanRun] = useState(false)

  // Modify mode
  const [modifyMode, setModifyMode] = useState(false)
  const [modifyInstruction, setModifyInstruction] = useState('')

  const { setWorkflow, workflow, serverVersion } = useStudioStore()
  const { startExecution, status: execStatus } = useExecutionStore()

  const isRunning = execStatus === 'running'

  /** Generate preview (v2) */
  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setError(null)
    setApplied(false)
    setCanRun(false)

    try {
      const result = await api.agentGeneratePreview_v2(prompt)
      setPreview(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成失败')
    } finally {
      setLoading(false)
    }
  }, [prompt])

  /** Modify existing workflow via natural language (v2) */
  const handleModify = useCallback(async () => {
    if (!modifyInstruction.trim()) return
    if (!workflow.id) return
    setLoading(true)
    setError(null)
    setApplied(false)
    setCanRun(false)

    try {
      const result = await api.agentModifyPreview_v2(workflow.id, modifyInstruction)
      setPreview(result)
      setModifyMode(false)
      setModifyInstruction('')
    } catch (e) {
      setError(e instanceof Error ? e.message : '修改失败')
    } finally {
      setLoading(false)
    }
  }, [modifyInstruction, workflow.id])

  /** Apply v2 preview with undo snapshot and version conflict handling */
  const handleApply = useCallback(async () => {
    if (!preview?.intent) return
    setApplying(true)
    setError(null)

    // Save undo snapshot before applying
    setUndoSnapshot(structuredClone(workflow))

    try {
      const result = await api.agentApply_v2(preview.intent, {
        workflowId: workflow.id,
        expectedVersion: serverVersion ?? undefined,
      })

      if (!result.success) {
        const msg = result.error ?? '应用失败'
        if (msg.includes('409') || msg.includes('冲突') || msg.includes('conflict') || msg.includes('stale') || msg.includes('version')) {
          setError('工作流已被更新，请刷新后重试')
        } else {
          setError(msg)
        }
        setUndoSnapshot(null)
        return
      }

      // If we have a compiled_workflow from the preview, use it directly
      if (preview.compiled_workflow) {
        setWorkflow(preview.compiled_workflow)
      } else {
        // Reload from server to get the latest version
        await useStudioStore.getState().loadFromServer(result.workflow_id)
      }

      setPreview(null)
      setPrompt('')
      setApplied(true)
      setCanRun(true)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '应用失败'
      if (msg.includes('409') || msg.includes('冲突') || msg.includes('conflict') || msg.includes('stale') || msg.includes('version')) {
        setError('工作流已被更新，请刷新后重试')
      } else {
        setError(msg)
      }
      setUndoSnapshot(null)
    } finally {
      setApplying(false)
    }
  }, [preview, workflow, serverVersion, setWorkflow])

  /** Undo agent changes by restoring the pre-apply snapshot */
  const handleUndo = useCallback(() => {
    if (undoSnapshot) {
      setWorkflow(undoSnapshot)
      setUndoSnapshot(null)
      setApplied(false)
      setCanRun(false)
      setPreview(null)
      setError(null)
    }
  }, [undoSnapshot, setWorkflow])

  /** Run workflow after successful apply */
  const handleRun = useCallback(() => {
    startExecution(workflow.id)
  }, [startExecution, workflow.id])

  const handleCancel = useCallback(() => {
    setPreview(null)
    setError(null)
  }, [])

  const toggleModifyMode = useCallback(() => {
    setModifyMode(prev => !prev)
    setModifyInstruction('')
    setError(null)
  }, [])

  if (!open) {
    return (
      <button className="agent-fab" onClick={() => setOpen(true)} aria-label="打开 Agent">
        <Robot size={21} />
      </button>
    )
  }

  const hasErrors = (preview?.validation_errors?.length ?? 0) > 0
  const canApply = preview?.can_apply ?? false

  return (
    <section className="agent-composer" role="region" aria-label="Workflow Agent">
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
          {loading ? '生成中...' : '生成'}
        </button>
      </div>

      {error && (
        <div className="agent-error" role="alert">
          <Warning size={13} /> {error}
        </div>
      )}

      {/* Success banner with undo + run */}
      {applied && !preview && (
        <div className="agent-success-banner">
          <CheckCircle size={14} weight="fill" />
          <span>已应用</span>
          <div className="agent-success-actions">
            {undoSnapshot && (
              <button className="agent-undo-btn" onClick={handleUndo} aria-label="撤销 Agent 更改">
                <ArrowsClockwise size={12} /> 撤销
              </button>
            )}
            {canRun && !isRunning && (
              <button className="agent-run-btn" onClick={handleRun} aria-label="运行工作流">
                <Play size={12} weight="fill" /> 运行
              </button>
            )}
          </div>
        </div>
      )}

      {preview && (
        <div className="agent-preview">
          {/* Warnings */}
          <Warnings warnings={preview.warnings} />

          {/* Validation errors */}
          <ValidationErrors errors={preview.validation_errors} />

          {/* Intent structure (v2) */}
          {preview.intent && <IntentPreview intent={preview.intent} />}

          {/* Compiled workflow (v2) */}
          {preview.compiled_workflow && <CompiledWorkflowPreview spec={preview.compiled_workflow} />}

          {/* Repair steps */}
          <RepairPreview steps={preview.repair_steps} />

          {/* Cost estimate (v2) */}
          {preview.cost_estimate && <CostPreview cost={preview.cost_estimate} />}

          {/* Destructive warning */}
          {!preview.can_apply && (
            <div className="agent-destructive-warning">
              <Warning size={13} weight="fill" /> 此操作存在验证问题，无法安全应用
            </div>
          )}

          {/* Actions */}
          <div className="agent-preview-actions">
            <button
              className={`agent-apply-btn ${!canApply || applying ? 'disabled' : ''}`}
              onClick={handleApply}
              disabled={!canApply || applying}
            >
              <CheckCircle size={14} /> {applying ? '应用中...' : canApply ? '确认应用' : '无法应用'}
            </button>
            <button className="agent-cancel-btn" onClick={handleCancel} disabled={applying}>取消</button>
          </div>
        </div>
      )}

      {/* Modify mode toggle */}
      {!preview && !applied && (
        <div className="agent-modify-toggle">
          <button className="agent-cancel-btn" onClick={toggleModifyMode}>
            {modifyMode ? '取消修改' : '修改现有工作流'}
          </button>
        </div>
      )}

      {/* Modify instruction input */}
      {modifyMode && !preview && (
        <div className="agent-input agent-modify-input">
          <textarea
            value={modifyInstruction}
            onChange={(e) => setModifyInstruction(e.target.value)}
            placeholder="描述想要修改的内容..."
            rows={2}
            aria-label="修改指令"
          />
          <button onClick={handleModify} disabled={loading || !modifyInstruction.trim()}>
            <Sparkle size={17} weight="fill" />
            {loading ? '分析中...' : '修改'}
          </button>
        </div>
      )}

      {/* Undo bar (when snapshot exists but no active preview) */}
      {!preview && undoSnapshot && !applied && (
        <div className="agent-undo-bar">
          <button className="agent-undo-btn" onClick={handleUndo} aria-label="撤销 Agent 更改">
            <ArrowsClockwise size={12} /> 撤销 Agent 更改
          </button>
        </div>
      )}
    </section>
  )
}
