import { useCallback, useState } from 'react'
import { Robot, Sparkle, Warning, CheckCircle, Pencil, ArrowRight, TreeStructure, Play, ArrowsClockwise, Plus, Minus, Cube } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import { useExecutionStore } from '../stores/executionStore'
import * as api from '../api'
import type { AgentPreviewResponse_v2, WorkflowIntent, WorkflowSpec, GraphPatch, ModuleDiffEntry, ValidationError, RepairStep, CostEstimate } from '../api'
import type { StudioNode, EnhancedEdge, StudioNodeData } from '../types'

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
            {n.moduleId && (
              <span className="agent-intent-module" title="模块">
                <Cube size={9} /> {n.moduleId}{n.moduleVersion ? `@${n.moduleVersion}` : ''}
              </span>
            )}
          </span>
        ))}
      </div>
      {/* 模块字段（moduleId/moduleVersion/configOverrides） */}
      {intent.nodes.some((n) => n.moduleId || n.moduleVersion || (n.configOverrides && Object.keys(n.configOverrides).length > 0)) && (
        <div className="agent-intent-conns">
          {intent.nodes.map((n) => {
            const overrideKeys = n.configOverrides ? Object.keys(n.configOverrides) : []
            if (!n.moduleId && !n.moduleVersion && overrideKeys.length === 0) return null
            return (
              <div key={n.alias} className="agent-intent-conn">
                <span className="agent-intent-alias">{n.alias}</span>
                {n.moduleId && <span className="agent-intent-module">{n.moduleId}</span>}
                {n.moduleVersion && <span className="agent-intent-module">@{n.moduleVersion}</span>}
                {overrideKeys.length > 0 && (
                  <span className="agent-intent-override" title={JSON.stringify(n.configOverrides)}>
                    覆盖 {overrideKeys.join(', ')}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      )}
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
        变更内容（增量 Diff）
      </div>
      {patch.description && <div className="agent-patch-desc">{patch.description}</div>}
      <div className="agent-patch-list">
        {patch.add_nodes.map((n, i) => {
          const rec = n as { id?: string; label?: string; kind?: string; data?: { label?: string; kind?: string } }
          const label = rec.data?.label ?? rec.label ?? rec.data?.kind ?? rec.kind ?? rec.id ?? '?'
          return (
            <div key={i} className="agent-patch-item agent-patch-add">
              <Plus size={11} /> 添加节点 <strong>{label}</strong>
              {rec.id && <code>{rec.id}</code>}
            </div>
          )
        })}
        {patch.remove_nodes.map((id, i) => (
          <div key={i} className="agent-patch-item agent-patch-remove">
            <Minus size={11} /> 删除节点 <code>{id}</code>
          </div>
        ))}
        {patch.update_nodes.map((n, i) => {
          const rec = n as { id?: string; label?: string | null; config?: Record<string, unknown> | null }
          const configKeys = rec.config ? Object.keys(rec.config) : []
          return (
            <div key={i} className="agent-patch-item agent-patch-modify">
              <Pencil size={11} /> 修改节点 <code>{rec.id}</code>
              {rec.label != null && <span>标签 “{rec.label}”</span>}
              {configKeys.length > 0 && <span>配置 {configKeys.join(', ')}</span>}
            </div>
          )
        })}
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

/** Human-readable diff text (preview.diff). */
function DiffText({ diff }: { diff: string }) {
  return (
    <div className="agent-preview-section">
      <div className="agent-preview-title">
        <span className="agent-preview-icon"><Pencil size={12} /></span>
        差异文本
      </div>
      <div className="agent-preview-diff">
        <pre>{diff}</pre>
      </div>
    </div>
  )
}

const MODULE_DIFF_TYPE_LABELS: Record<ModuleDiffEntry['type'], string> = {
  added: '新增',
  removed: '移除',
  upgraded: '升级',
  reconfigured: '配置变更',
}

/** 渲染升级详情（ModuleDiff camelCase）中的字段/端口增减行。 */
function ModuleDiffDetailRows({ details }: { details: Record<string, unknown> }) {
  const addedFields = (details.addedFields as Array<Record<string, unknown>> | undefined) ?? []
  const removedFields = (details.removedFields as string[] | undefined) ?? []
  const changedFields = (details.changedFields as Array<Record<string, unknown>> | undefined) ?? []
  const addedPorts = (details.addedPorts as Array<Record<string, unknown>> | undefined) ?? []
  const removedPorts = (details.removedPorts as string[] | undefined) ?? []
  const changedPorts = (details.changedPorts as Array<Record<string, unknown>> | undefined) ?? []
  const breaking = Boolean(details.breaking)

  if (
    !breaking &&
    addedFields.length === 0 && removedFields.length === 0 && changedFields.length === 0 &&
    addedPorts.length === 0 && removedPorts.length === 0 && changedPorts.length === 0
  ) {
    return <div className="agent-patch-item">无字段/端口变更</div>
  }

  return (
    <>
      {breaking && (
        <div className="agent-patch-item agent-patch-remove">
          <Warning size={11} weight="fill" /> 破坏性升级（可能需要手动调整）
        </div>
      )}
      {addedFields.map((f, i) => (
        <div key={`af-${i}`} className="agent-patch-item agent-patch-add">
          <Plus size={11} /> 字段 <code>{String(f.key ?? f.field ?? '?')}</code>
        </div>
      ))}
      {removedFields.map((key, i) => (
        <div key={`rf-${i}`} className="agent-patch-item agent-patch-remove">
          <Minus size={11} /> 字段 <code>{key}</code>
        </div>
      ))}
      {changedFields.map((f, i) => (
        <div key={`cf-${i}`} className="agent-patch-item agent-patch-modify">
          <Pencil size={11} /> 字段 <code>{String(f.field ?? f.key ?? '?')}</code> 变更
        </div>
      ))}
      {addedPorts.map((p, i) => (
        <div key={`ap-${i}`} className="agent-patch-item agent-patch-add">
          <Plus size={11} /> 端口 <code>{String(p.id ?? '?')}</code>
        </div>
      ))}
      {removedPorts.map((pid, i) => (
        <div key={`rp-${i}`} className="agent-patch-item agent-patch-remove">
          <Minus size={11} /> 端口 <code>{pid}</code>
        </div>
      ))}
      {changedPorts.map((p, i) => (
        <div key={`cp-${i}`} className="agent-patch-item agent-patch-modify">
          <Pencil size={11} /> 端口 <code>{String(p.portId ?? p.id ?? '?')}</code> 变更
        </div>
      ))}
    </>
  )
}

/** 模块/版本/配置 diff 区（preview.module_diffs）。 */
function ModuleDiffs({ entries }: { entries: ModuleDiffEntry[] }) {
  if (!entries || entries.length === 0) return null
  return (
    <div className="agent-preview-section">
      <div className="agent-preview-title">
        <span className="agent-preview-icon"><Cube size={12} /></span>
        模块变更
      </div>
      <div className="agent-patch-list">
        {entries.map((e, i) => {
          const typeClass =
            e.type === 'added' ? 'agent-patch-add' :
            e.type === 'removed' ? 'agent-patch-remove' :
            'agent-patch-modify'
          const changedKeys = e.details?.changedKeys as string[] | undefined
          return (
            <div key={i} className="agent-module-diff">
              <div className={`agent-patch-item ${typeClass}`}>
                <span className="agent-module-diff-badge">{MODULE_DIFF_TYPE_LABELS[e.type]}</span>
                <code>{e.moduleId}</code>
                <span className="agent-intent-alias">节点 {e.nodeId}</span>
                {(e.from || e.to) && (
                  <span className="agent-module-diff-versions">
                    {e.from ?? '—'} → {e.to ?? '—'}
                  </span>
                )}
              </div>
              {e.type === 'upgraded' && e.details && (
                <div className="agent-module-diff-details">
                  <ModuleDiffDetailRows details={e.details} />
                </div>
              )}
              {e.type === 'reconfigured' && e.details && (
                <div className="agent-module-diff-details">
                  <div className="agent-patch-item agent-patch-modify">
                    <Pencil size={11} /> 配置键 {Array.isArray(changedKeys) ? changedKeys.join(', ') : String(changedKeys ?? '')}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ==================== Patch application ==================== */

/**
 * 本地应用 GraphPatch（与后端 /agent/apply-patch 语义一致）：
 * 删除 remove_nodes/remove_edges，更新 update_nodes 的 label/config，
 * 追加 add_nodes/add_edges；其余节点及其 id 原样保留（修改不重建）。
 */
function applyGraphPatch(workflow: WorkflowSpec, patch: GraphPatch): WorkflowSpec {
  const removeNodeIds = new Set(patch.remove_nodes)
  const removeEdgeIds = new Set(patch.remove_edges)

  const nodes = workflow.nodes
    .filter((n) => !removeNodeIds.has(n.id))
    .map((node) => {
      const update = patch.update_nodes.find(
        (u) => (u as { id?: string }).id === node.id,
      ) as { id?: string; label?: string | null; config?: Record<string, unknown> | null } | undefined
      if (!update) return node
      const data = { ...node.data } as StudioNodeData
      if (update.label != null) data.label = update.label
      if (update.config != null) data.config = update.config as StudioNodeData['config']
      return { ...node, data }
    })

  // 删除连线：显式 id + 端点被删的连线
  const edges = workflow.edges.filter(
    (e) => !removeEdgeIds.has(e.id) && !removeNodeIds.has(e.source) && !removeNodeIds.has(e.target),
  )

  return {
    ...workflow,
    nodes: [...nodes, ...(patch.add_nodes as unknown as StudioNode[])],
    edges: [...edges, ...(patch.add_edges as unknown as EnhancedEdge[])],
  }
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

  // Destructive op: require explicit confirmation before apply
  const [pendingDestructive, setPendingDestructive] = useState(false)

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
    setPendingDestructive(false)

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
    setPendingDestructive(false)

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
    setPendingDestructive(false)

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

      // Modify: apply patch locally — 修改不重建，未触及的节点 id 保留
      if (preview.patch) {
        setWorkflow(applyGraphPatch(workflow, preview.patch))
      } else if (preview.compiled_workflow) {
        // Generate: full replace
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
    setPendingDestructive(false)
  }, [])

  /** Apply click: destructive ops need an explicit confirmation step first. */
  const handleApplyClick = useCallback(() => {
    if (preview?.destructive && !pendingDestructive) {
      setPendingDestructive(true)
      return
    }
    void handleApply()
  }, [preview?.destructive, pendingDestructive, handleApply])

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

          {/* Modify: incremental diff is the primary view (修改不重建) */}
          {preview.patch && <PatchPreview patch={preview.patch} />}

          {/* Generate: full graph listing */}
          {!preview.patch && preview.compiled_workflow && <CompiledWorkflowPreview spec={preview.compiled_workflow} />}

          {/* Human-readable diff text */}
          {preview.diff && <DiffText diff={preview.diff} />}

          {/* Module / version / config diffs */}
          {preview.module_diffs && preview.module_diffs.length > 0 && (
            <ModuleDiffs entries={preview.module_diffs} />
          )}

          {/* Repair steps */}
          <RepairPreview steps={preview.repair_steps} />

          {/* Cost estimate (v2) */}
          {preview.cost_estimate && <CostPreview cost={preview.cost_estimate} />}

          {/* Validation failure: blocks apply outright */}
          {!preview.can_apply && (
            <div className="agent-destructive-warning">
              <Warning size={13} weight="fill" /> 此操作存在验证问题，无法安全应用
            </div>
          )}

          {/* Destructive op: allowed, but requires confirmation */}
          {preview.destructive && (
            <div className="agent-destructive-warning" role="alert">
              <Warning size={13} weight="fill" />
              <div>
                <div>此操作包含删除（破坏性变更），应用前需二次确认</div>
                {preview.patch && (preview.patch.remove_nodes.length > 0 || preview.patch.remove_edges.length > 0) && (
                  <div className="agent-destructive-list">
                    {preview.patch.remove_nodes.map((id) => (
                      <div key={id} className="agent-patch-item agent-patch-remove">
                        <Minus size={11} /> 将删除节点 <code>{id}</code>
                      </div>
                    ))}
                    {preview.patch.remove_edges.map((id) => (
                      <div key={id} className="agent-patch-item agent-patch-remove">
                        <Minus size={11} /> 将删除连线 <code>{id}</code>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Destructive confirmation (second step) */}
          {preview.destructive && pendingDestructive ? (
            <div className="agent-destructive-confirm" role="alertdialog" aria-label="确认破坏性操作">
              <div className="agent-destructive-confirm-title">
                <Warning size={13} weight="fill" /> 确认删除以下内容并应用？
              </div>
              <div className="agent-destructive-list">
                {(preview.patch?.remove_nodes ?? []).map((id) => (
                  <div key={id} className="agent-patch-item agent-patch-remove">
                    <Minus size={11} /> 删除节点 <code>{id}</code>
                  </div>
                ))}
                {(preview.patch?.remove_edges ?? []).map((id) => (
                  <div key={id} className="agent-patch-item agent-patch-remove">
                    <Minus size={11} /> 删除连线 <code>{id}</code>
                  </div>
                ))}
              </div>
              <div className="agent-preview-actions">
                <button
                  className={`agent-apply-btn ${applying ? 'disabled' : ''}`}
                  onClick={handleApply}
                  disabled={applying}
                >
                  <CheckCircle size={14} /> {applying ? '应用中...' : '确认删除并应用'}
                </button>
                <button className="agent-cancel-btn" onClick={() => setPendingDestructive(false)} disabled={applying}>
                  取消
                </button>
              </div>
            </div>
          ) : (
            /* Actions */
            <div className="agent-preview-actions">
              <button
                className={`agent-apply-btn ${!canApply || applying ? 'disabled' : ''}`}
                onClick={handleApplyClick}
                disabled={!canApply || applying}
              >
                <CheckCircle size={14} /> {applying ? '应用中...' : canApply ? '确认应用' : '无法应用'}
              </button>
              <button className="agent-cancel-btn" onClick={handleCancel} disabled={applying}>取消</button>
            </div>
          )}
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
