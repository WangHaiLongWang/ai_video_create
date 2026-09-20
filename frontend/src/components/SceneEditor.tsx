/**
 * SceneEditor — Scene bundle editor panel
 *
 * Provides visual editing for scene bundles:
 * - Scene list with compact cards
 * - Click-to-expand edit forms
 * - Batch editing of shared fields
 * - Validation warnings
 * - Lock/unlock scenes
 */

import { useState, useCallback, useEffect, useMemo } from 'react'
import {
  CaretDown,
  CaretRight,
  Check,
  Copy,
  FilmStrip,
  Lock,
  LockOpen,
  MagnifyingGlass,
  PencilSimple,
  Plus,
  Warning,
  X,
  CheckSquare,
  Square,
  ArrowUp,
  ArrowDown,
  Trash,
  ListChecks,
} from '@phosphor-icons/react'
import * as api from '../api'
import type { SceneEntry, ScenePromptBundle } from '../schemas/scene-bundle'
import { useStudioStore } from '../store'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SceneEditorProps {
  onClose: () => void
}

interface SceneValidationIssue {
  sceneIndex: number
  field: string
  message: string
  severity: 'warning' | 'error'
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function generateSceneId(): string {
  return crypto.randomUUID().slice(0, 12)
}

function createEmptyScene(index: number): SceneEntry {
  return {
    sceneId: generateSceneId(),
    index,
    title: `Scene ${index + 1}`,
    narration: '',
    durationSeconds: 5,
    locked: false,
    image: { prompt: '', negativePrompt: '' },
    video: { prompt: '', duration: 5, resolution: '480P', ratio: '16:9' },
  }
}

function validateScenes(scenes: SceneEntry[]): SceneValidationIssue[] {
  const issues: SceneValidationIssue[] = []
  scenes.forEach((scene, i) => {
    if (!scene.title.trim()) {
      issues.push({ sceneIndex: i, field: 'title', message: 'Title is empty', severity: 'warning' })
    }
    if (!scene.narration.trim()) {
      issues.push({ sceneIndex: i, field: 'narration', message: 'Narration is empty', severity: 'warning' })
    }
    if (scene.durationSeconds <= 0) {
      issues.push({ sceneIndex: i, field: 'duration', message: 'Duration must be > 0', severity: 'error' })
    }
    if (!scene.image.prompt.trim()) {
      issues.push({ sceneIndex: i, field: 'image.prompt', message: 'Image prompt is empty', severity: 'warning' })
    }
    if (!scene.video.prompt.trim()) {
      issues.push({ sceneIndex: i, field: 'video.prompt', message: 'Video prompt is empty', severity: 'warning' })
    }
  })
  return issues
}

function getNarrationSnippet(text: string, maxLen = 80): string {
  if (!text) return '(no narration)'
  const clean = text.replace(/\s+/g, ' ').trim()
  return clean.length > maxLen ? clean.slice(0, maxLen) + '...' : clean
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Inline field editor for a single scene */
function SceneField({
  label,
  value,
  onChange,
  type = 'text',
  disabled = false,
  rows,
  readOnly = false,
  mono = false,
}: {
  label: string
  value: string | number
  onChange: (v: string | number) => void
  type?: 'text' | 'textarea' | 'number' | 'select'
  disabled?: boolean
  rows?: number
  readOnly?: boolean
  mono?: boolean
}) {
  const baseStyle: React.CSSProperties = {
    width: '100%',
    minHeight: type === 'textarea' ? 60 : 34,
    border: '1px solid #3b4038',
    borderRadius: 7,
    padding: '7px 9px',
    color: disabled ? '#5a6055' : '#e3e6dd',
    background: disabled ? '#1b1e1a' : '#171916',
    resize: type === 'textarea' ? 'vertical' : undefined,
    fontFamily: mono ? '"Cascadia Code", monospace' : undefined,
    fontSize: mono ? 11 : undefined,
  }

  return (
    <label className="se-field">
      <span className="se-field-label">{label}</span>
      {type === 'textarea' ? (
        <textarea
          rows={rows ?? 3}
          value={String(value)}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled || readOnly}
          readOnly={readOnly}
          style={baseStyle}
        />
      ) : type === 'number' ? (
        <input
          type="number"
          value={String(value)}
          onChange={(e) => onChange(e.target.value === '' ? 0 : Number(e.target.value))}
          disabled={disabled || readOnly}
          readOnly={readOnly}
          style={baseStyle}
        />
      ) : type === 'select' ? (
        <select
          value={String(value)}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled || readOnly}
          style={{ ...baseStyle, cursor: readOnly ? 'not-allowed' : 'pointer' }}
        >
          <option value="480P">480P</option>
          <option value="720P">720P</option>
          <option value="1080P">1080P</option>
          <option value="4K">4K</option>
        </select>
      ) : (
        <input
          type="text"
          value={String(value)}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled || readOnly}
          readOnly={readOnly}
          style={baseStyle}
        />
      )}
    </label>
  )
}

/** Single scene card — compact view with expand to edit */
function SceneCard({
  scene,
  index,
  totalScenes,
  isExpanded,
  isSelected,
  isBatchSelected,
  validationIssues,
  onToggleExpand,
  onUpdate,
  onToggleLock,
  onToggleBatchSelect,
  onMoveUp,
  onMoveDown,
  onDelete,
}: {
  scene: SceneEntry
  index: number
  totalScenes: number
  isExpanded: boolean
  isSelected: boolean
  isBatchSelected: boolean
  validationIssues: SceneValidationIssue[]
  onToggleExpand: () => void
  onUpdate: (updates: Partial<SceneEntry>) => void
  onToggleLock: () => void
  onToggleBatchSelect: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  onDelete: () => void
}) {
  const [showNegativePrompt, setShowNegativePrompt] = useState(false)

  const errorCount = validationIssues.filter((i) => i.severity === 'error').length
  const warnCount = validationIssues.filter((i) => i.severity === 'warning').length
  const hasIssues = errorCount > 0 || warnCount > 0

  const isLocked = scene.locked

  const handleUpdate = useCallback(
    <K extends keyof SceneEntry>(key: K, value: SceneEntry[K]) => {
      onUpdate({ [key]: value } as Partial<SceneEntry>)
    },
    [onUpdate],
  )

  const handleImagePromptChange = useCallback(
    (v: string | number) => onUpdate({ image: { ...scene.image, prompt: String(v) } }),
    [scene.image, onUpdate],
  )

  const handleImageNegChange = useCallback(
    (v: string | number) => onUpdate({ image: { ...scene.image, negativePrompt: String(v) } }),
    [scene.image, onUpdate],
  )

  const handleVideoPromptChange = useCallback(
    (v: string | number) => onUpdate({ video: { ...scene.video, prompt: String(v) } }),
    [scene.video, onUpdate],
  )

  const handleVideoDurationChange = useCallback(
    (v: string | number) => onUpdate({ video: { ...scene.video, duration: Number(v) } }),
    [scene.video, onUpdate],
  )

  const handleVideoResChange = useCallback(
    (v: string | number) => onUpdate({ video: { ...scene.video, resolution: String(v) } }),
    [scene.video, onUpdate],
  )

  return (
    <div
      className={`scene-card ${isExpanded ? 'scene-card--expanded' : ''} ${isSelected ? 'scene-card--selected' : ''} ${isLocked ? 'scene-card--locked' : ''}`}
    >
      {/* Compact header */}
      <div className="scene-card-header" onClick={onToggleExpand}>
        <div className="scene-card-header-left">
          <button
            className="scene-card-batch-check"
            onClick={(e) => { e.stopPropagation(); onToggleBatchSelect() }}
            title={isBatchSelected ? 'Deselect from batch' : 'Select for batch edit'}
          >
            {isBatchSelected ? <CheckSquare size={14} weight="fill" /> : <Square size={14} />}
          </button>

          <span className="scene-card-index">#{index + 1}</span>

          <span className="scene-card-title-text" title={scene.title}>
            {scene.title || '(untitled)'}
          </span>

          {isLocked && (
            <span className="scene-card-lock-badge" title="Locked">
              <Lock size={11} weight="fill" />
            </span>
          )}

          {hasIssues && (
            <span className="scene-card-warn-badge" title={`${warnCount} warnings, ${errorCount} errors`}>
              <Warning size={12} />
            </span>
          )}
        </div>

        <div className="scene-card-header-right">
          <span className="scene-card-duration">{scene.durationSeconds}s</span>
          {isExpanded ? <CaretDown size={14} /> : <CaretRight size={14} />}
        </div>
      </div>

      {/* Hover preview — shown when collapsed */}
      {!isExpanded && (
        <div className="scene-card-preview" title={scene.narration}>
          {getNarrationSnippet(scene.narration)}
        </div>
      )}

      {/* Expanded edit form */}
      {isExpanded && (
        <div className="scene-card-body">
          {/* Scene reorder + actions bar */}
          <div className="scene-card-actions-bar">
            <button
              className="scene-action-btn"
              onClick={onMoveUp}
              disabled={index === 0}
              title="Move up"
            >
              <ArrowUp size={14} />
            </button>
            <button
              className="scene-action-btn"
              onClick={onMoveDown}
              disabled={index === totalScenes - 1}
              title="Move down"
            >
              <ArrowDown size={14} />
            </button>
            <button
              className={`scene-action-btn ${isLocked ? 'scene-action-btn--active' : ''}`}
              onClick={onToggleLock}
              title={isLocked ? 'Unlock scene' : 'Lock scene'}
            >
              {isLocked ? <Lock size={14} weight="fill" /> : <LockOpen size={14} />}
            </button>
            <button
              className="scene-action-btn scene-action-btn--danger"
              onClick={onDelete}
              title="Delete scene"
            >
              <Trash size={14} />
            </button>
          </div>

          {/* Basic fields */}
          <div className="scene-card-fields">
            <SceneField
              label="Title"
              value={scene.title}
              onChange={(v) => handleUpdate('title', String(v))}
              disabled={isLocked}
            />
            <SceneField
              label="Narration"
              value={scene.narration}
              onChange={(v) => handleUpdate('narration', String(v))}
              type="textarea"
              rows={3}
              disabled={isLocked}
            />
            <SceneField
              label="Duration (seconds)"
              value={scene.durationSeconds}
              onChange={(v) => handleUpdate('durationSeconds', Number(v))}
              type="number"
              disabled={isLocked}
            />
          </div>

          {/* Image section */}
          <div className="scene-card-section">
            <div className="scene-card-section-header">
              <span>Image Generation</span>
            </div>
            <div className="scene-card-fields">
              <SceneField
                label="Prompt"
                value={scene.image.prompt}
                onChange={handleImagePromptChange}
                type="textarea"
                rows={3}
                disabled={isLocked}
              />
              <div>
                <button
                  className="scene-neg-toggle"
                  onClick={() => setShowNegativePrompt(!showNegativePrompt)}
                >
                  {showNegativePrompt ? <CaretDown size={12} /> : <CaretRight size={12} />}
                  Negative prompt
                </button>
                {showNegativePrompt && (
                  <SceneField
                    label=""
                    value={scene.image.negativePrompt ?? ''}
                    onChange={handleImageNegChange}
                    type="textarea"
                    rows={2}
                    disabled={isLocked}
                    mono
                  />
                )}
              </div>
              {scene.image.provider && (
                <div className="scene-readonly-info">
                  Provider: {scene.image.provider} / {scene.image.model ?? '-'}
                </div>
              )}
            </div>
          </div>

          {/* Video section */}
          <div className="scene-card-section">
            <div className="scene-card-section-header">
              <span>Video Generation</span>
            </div>
            <div className="scene-card-fields">
              <SceneField
                label="Prompt"
                value={scene.video.prompt}
                onChange={handleVideoPromptChange}
                type="textarea"
                rows={3}
                disabled={isLocked}
              />
              <div className="scene-card-row">
                <SceneField
                  label="Duration (s)"
                  value={scene.video.duration ?? scene.durationSeconds}
                  onChange={handleVideoDurationChange}
                  type="number"
                  disabled={isLocked}
                />
                <SceneField
                  label="Resolution"
                  value={scene.video.resolution ?? '480P'}
                  onChange={handleVideoResChange}
                  type="select"
                  disabled={isLocked}
                />
              </div>
              {scene.video.provider && (
                <div className="scene-readonly-info">
                  Provider: {scene.video.provider} / {scene.video.model ?? '-'}
                </div>
              )}
            </div>
          </div>

          {/* Validation issues */}
          {validationIssues.length > 0 && (
            <div className="scene-card-validation">
              {validationIssues.map((issue, vi) => (
                <div key={vi} className={`scene-validation-item scene-validation-item--${issue.severity}`}>
                  <Warning size={12} />
                  <span>{issue.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Batch edit panel
// ---------------------------------------------------------------------------

function BatchEditPanel({
  scenes,
  selectedIndices,
  onUpdate,
  onClearSelection,
}: {
  scenes: SceneEntry[]
  selectedIndices: Set<number>
  onUpdate: (indices: number[], updates: Partial<SceneEntry>) => void
  onClearSelection: () => void
}) {
  const [narration, setNarration] = useState('')
  const [duration, setDuration] = useState<number>(5)
  const [imagePrompt, setImagePrompt] = useState('')
  const [videoPrompt, setVideoPrompt] = useState('')

  const applyBatch = useCallback(() => {
    const indices = Array.from(selectedIndices)
    const updates: Partial<SceneEntry> = {}
    if (narration) updates.narration = narration
    if (duration > 0) updates.durationSeconds = duration
    if (imagePrompt) updates.image = { ...scenes[indices[0]]?.image, prompt: imagePrompt }
    if (videoPrompt) updates.video = { ...scenes[indices[0]]?.video, prompt: videoPrompt }
    onUpdate(indices, updates)
  }, [narration, duration, imagePrompt, videoPrompt, selectedIndices, scenes, onUpdate])

  return (
    <div className="batch-edit-panel">
      <div className="batch-edit-header">
        <span className="batch-edit-title">
          <ListChecks size={14} />
          Batch Edit ({selectedIndices.size} scenes)
        </span>
        <button className="batch-edit-close" onClick={onClearSelection}>
          <X size={14} />
        </button>
      </div>
      <div className="batch-edit-fields">
        <SceneField
          label="Narration (leave empty to skip)"
          value={narration}
          onChange={(v) => setNarration(String(v))}
          type="textarea"
          rows={2}
        />
        <SceneField
          label="Duration (seconds)"
          value={duration}
          onChange={(v) => setDuration(Number(v))}
          type="number"
        />
        <SceneField
          label="Image Prompt (leave empty to skip)"
          value={imagePrompt}
          onChange={(v) => setImagePrompt(String(v))}
          type="textarea"
          rows={2}
        />
        <SceneField
          label="Video Prompt (leave empty to skip)"
          value={videoPrompt}
          onChange={(v) => setVideoPrompt(String(v))}
          type="textarea"
          rows={2}
        />
      </div>
      <div className="batch-edit-actions">
        <button className="batch-apply-btn" onClick={applyBatch}>
          <Check size={14} />
          Apply to selected
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main SceneEditor
// ---------------------------------------------------------------------------

export function SceneEditor({ onClose }: SceneEditorProps) {
  const workflow = useStudioStore((s) => s.workflow)

  // State
  const [scenes, setScenes] = useState<SceneEntry[]>([])
  const [draftId, setDraftId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)
  const [batchSelectedIndices, setBatchSelectedIndices] = useState<Set<number>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)

  // Load or create scene draft
  useEffect(() => {
    let cancelled = false
    async function loadDrafts() {
      setLoading(true)
      setError(null)
      try {
        const drafts = await api.listSceneDrafts(workflow.id)
        if (cancelled) return
        if (drafts.length > 0) {
          // Load the latest draft
          const latest = drafts[0]
          setDraftId(latest.draft_id)
          const bundleData = await api.getSceneDraft(workflow.id, latest.draft_id)
          if (cancelled) return
          setScenes((bundleData.scenes as SceneEntry[]) ?? [])
        } else {
          // No drafts yet — create a starter bundle with scenes from storyboard nodes
          const storyboardNodes = workflow.nodes.filter((n) => n.data.kind === 'storyboard')
          if (storyboardNodes.length > 0) {
            // Create initial scenes from storyboard config
            const initial: SceneEntry[] = storyboardNodes.map((node, i) => {
              const cfg = node.data.config
              return {
                sceneId: node.id,
                index: i,
                title: String(cfg.title ?? `Scene ${i + 1}`),
                narration: String(cfg.narration ?? ''),
                durationSeconds: Number(cfg.duration ?? 5),
                locked: false,
                image: {
                  prompt: String(cfg.image_prompt ?? ''),
                  negativePrompt: String(cfg.image_negative ?? ''),
                  provider: String(cfg.image_provider ?? ''),
                  model: String(cfg.image_model ?? ''),
                },
                video: {
                  prompt: String(cfg.video_prompt ?? ''),
                  provider: String(cfg.video_provider ?? ''),
                  model: String(cfg.video_model ?? ''),
                  duration: Number(cfg.video_duration ?? 5),
                  resolution: String(cfg.video_resolution ?? '480P'),
                  ratio: String(cfg.video_ratio ?? '16:9'),
                },
              }
            })
            setScenes(initial)
          } else {
            // Create 3 starter scenes
            setScenes([0, 1, 2].map((i) => createEmptyScene(i)))
          }
        }
      } catch (err) {
        if (cancelled) return
        // API failed — fall back to creating scenes from storyboard nodes
        const storyboardNodes = workflow.nodes.filter((n) => n.data.kind === 'storyboard')
        if (storyboardNodes.length > 0) {
          const fallback: SceneEntry[] = storyboardNodes.map((node, i) => {
            const cfg = node.data.config
            return {
              sceneId: node.id,
              index: i,
              title: String(cfg.title ?? `Scene ${i + 1}`),
              narration: String(cfg.narration ?? ''),
              durationSeconds: Number(cfg.duration ?? 5),
              locked: false,
              image: {
                prompt: String(cfg.image_prompt ?? ''),
                negativePrompt: String(cfg.image_negative ?? ''),
                provider: String(cfg.image_provider ?? ''),
                model: String(cfg.image_model ?? ''),
              },
              video: {
                prompt: String(cfg.video_prompt ?? ''),
                provider: String(cfg.video_provider ?? ''),
                model: String(cfg.video_model ?? ''),
                duration: Number(cfg.video_duration ?? 5),
                resolution: String(cfg.video_resolution ?? '480P'),
                ratio: String(cfg.video_ratio ?? '16:9'),
              },
            }
          })
          setScenes(fallback)
        } else {
          setScenes([0, 1, 2].map((i) => createEmptyScene(i)))
        }
        // Still show a non-blocking warning about the API issue
        setError(err instanceof Error ? err.message : 'Failed to load scene drafts')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    loadDrafts()
    return () => { cancelled = true }
  }, [workflow.id, workflow.nodes])

  // Validation
  const validationIssues = useMemo(() => validateScenes(scenes), [scenes])

  // Filtered scenes
  const filteredScenes = useMemo(() => {
    if (!searchQuery.trim()) return scenes.map((s, i) => ({ scene: s, originalIndex: i }))
    const q = searchQuery.toLowerCase()
    return scenes
      .map((s, i) => ({ scene: s, originalIndex: i }))
      .filter(({ scene }) =>
        scene.title.toLowerCase().includes(q) ||
        scene.narration.toLowerCase().includes(q) ||
        scene.image.prompt.toLowerCase().includes(q) ||
        scene.video.prompt.toLowerCase().includes(q)
      )
  }, [scenes, searchQuery])

  // Handlers
  const handleUpdateScene = useCallback((index: number, updates: Partial<SceneEntry>) => {
    setScenes((prev) => prev.map((s, i) => (i === index ? { ...s, ...updates } : s)))
  }, [])

  const handleToggleLock = useCallback(async (index: number) => {
    const scene = scenes[index]
    if (!scene) return
    const newLocked = !scene.locked
    setScenes((prev) => prev.map((s, i) => (i === index ? { ...s, locked: newLocked } : s)))
    // Persist to server if we have a draft
    if (draftId) {
      try {
        if (newLocked) {
          await api.lockScene(workflow.id, draftId, index)
        } else {
          await api.unlockScene(workflow.id, draftId, index)
        }
      } catch (err) {
        console.error('Failed to toggle lock:', err)
      }
    }
  }, [scenes, draftId, workflow.id])

  const handleMoveUp = useCallback((index: number) => {
    if (index === 0) return
    setScenes((prev) => {
      const next = [...prev]
      const temp = next[index]
      next[index] = next[index - 1]
      next[index - 1] = temp
      // Update indices
      return next.map((s, i) => ({ ...s, index: i }))
    })
  }, [])

  const handleMoveDown = useCallback((index: number) => {
    setScenes((prev) => {
      if (index >= prev.length - 1) return prev
      const next = [...prev]
      const temp = next[index]
      next[index] = next[index + 1]
      next[index + 1] = temp
      return next.map((s, i) => ({ ...s, index: i }))
    })
  }, [])

  const handleDelete = useCallback((index: number) => {
    setScenes((prev) => prev.filter((_, i) => i !== index).map((s, i) => ({ ...s, index: i })))
    if (expandedIndex === index) setExpandedIndex(null)
    setBatchSelectedIndices((prev) => {
      const next = new Set<number>()
      prev.forEach((i) => {
        if (i < index) next.add(i)
        else if (i > index) next.add(i - 1)
      })
      return next
    })
  }, [expandedIndex])

  const handleAddScene = useCallback(() => {
    setScenes((prev) => [...prev, createEmptyScene(prev.length)])
  }, [])

  const handleToggleBatchSelect = useCallback((index: number) => {
    setBatchSelectedIndices((prev) => {
      const next = new Set(prev)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }, [])

  const handleBatchUpdate = useCallback((indices: number[], updates: Partial<SceneEntry>) => {
    setScenes((prev) =>
      prev.map((s, i) => (indices.includes(i) ? { ...s, ...updates } : s))
    )
  }, [])

  const handleSave = useCallback(async () => {
    if (!draftId) {
      // Create new draft
      setSaving(true)
      try {
        const bundle: ScenePromptBundle = {
          schemaVersion: '1.0',
          storyboardId: '',
          workflowId: workflow.id,
          executionId: '',
          title: workflow.name || 'Scene Draft',
          scenes,
          source: 'draft',
        }
        const result = await api.createSceneDraft(workflow.id, bundle as unknown as Record<string, unknown>)
        setDraftId(result.draft_id)
        setSaveMessage('Draft created')
        setTimeout(() => setSaveMessage(null), 2000)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to create draft')
      } finally {
        setSaving(false)
      }
    } else {
      // Update existing draft
      setSaving(true)
      try {
        const bundle: ScenePromptBundle = {
          schemaVersion: '1.0',
          storyboardId: '',
          workflowId: workflow.id,
          executionId: '',
          title: workflow.name || 'Scene Draft',
          scenes,
          source: 'draft',
        }
        await api.updateSceneDraft(workflow.id, draftId, {
          bundle: bundle as unknown as Record<string, unknown>,
        })
        setSaveMessage('Saved')
        setTimeout(() => setSaveMessage(null), 2000)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to save')
      } finally {
        setSaving(false)
      }
    }
  }, [draftId, scenes, workflow.id, workflow.name])

  const toggleSelectAll = useCallback(() => {
    if (batchSelectedIndices.size === scenes.length) {
      setBatchSelectedIndices(new Set())
    } else {
      setBatchSelectedIndices(new Set(scenes.map((_, i) => i)))
    }
  }, [batchSelectedIndices.size, scenes])

  const hasBatchSelection = batchSelectedIndices.size > 0

  // Stats
  const totalDuration = useMemo(() => scenes.reduce((sum, s) => sum + s.durationSeconds, 0), [scenes])
  const lockedCount = useMemo(() => scenes.filter((s) => s.locked).length, [scenes])
  const warnCount = validationIssues.filter((i) => i.severity === 'warning').length
  const errCount = validationIssues.filter((i) => i.severity === 'error').length

  return (
    <div className="scene-editor-overlay">
      <div className="scene-editor">
        {/* Header */}
        <div className="se-header">
          <div className="se-header-left">
            <FilmStrip size={16} weight="fill" style={{ color: 'var(--accent)' }} />
            <h2>Scene Editor</h2>
            <span className="se-header-count">{scenes.length} scenes</span>
          </div>
          <button className="se-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Toolbar */}
        <div className="se-toolbar">
          <div className="se-search">
            <MagnifyingGlass size={14} />
            <input
              type="text"
              placeholder="Search scenes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button className="se-search-clear" onClick={() => setSearchQuery('')}>
                <X size={12} />
              </button>
            )}
          </div>
          <div className="se-toolbar-actions">
            <button
              className="se-tool-btn"
              onClick={toggleSelectAll}
              title={batchSelectedIndices.size === scenes.length ? 'Deselect all' : 'Select all'}
            >
              {batchSelectedIndices.size === scenes.length ? <CheckSquare size={14} /> : <Square size={14} />}
              {batchSelectedIndices.size > 0 ? `${batchSelectedIndices.size}/${scenes.length}` : 'All'}
            </button>
            <button className="se-tool-btn se-add-btn" onClick={handleAddScene}>
              <Plus size={14} />
              Add
            </button>
            <button
              className="se-tool-btn se-save-btn"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Draft'}
            </button>
          </div>
        </div>

        {/* Stats bar */}
        <div className="se-stats">
          <span>{scenes.length} scenes</span>
          <span>{totalDuration}s total</span>
          {lockedCount > 0 && <span><Lock size={10} /> {lockedCount} locked</span>}
          {warnCount > 0 && <span className="se-stats-warn"><Warning size={10} /> {warnCount} warnings</span>}
          {errCount > 0 && <span className="se-stats-err"><Warning size={10} /> {errCount} errors</span>}
          {saveMessage && <span className="se-stats-saved">{saveMessage}</span>}
        </div>

        {/* Body */}
        <div className="se-body">
          {loading ? (
            <div className="se-loading">Loading scene drafts...</div>
          ) : error && scenes.length === 0 ? (
            <div className="se-error">
              <Warning size={16} />
              <span>{error}</span>
              <button onClick={() => setError(null)}>Dismiss</button>
            </div>
          ) : scenes.length === 0 ? (
            <div className="se-empty">
              <FilmStrip size={32} style={{ color: '#3a3f37' }} />
              <strong>No scenes yet</strong>
              <p>Click "Add" to create your first scene.</p>
            </div>
          ) : (
            <>
              {/* Non-blocking warning when fallback scenes loaded */}
              {error && (
                <div className="se-error" style={{ marginBottom: 8 }}>
                  <Warning size={14} />
                  <span>{error}</span>
                  <button onClick={() => setError(null)}>Dismiss</button>
                </div>
              )}

              {/* Batch edit panel */}
              {hasBatchSelection && (
                <BatchEditPanel
                  scenes={scenes}
                  selectedIndices={batchSelectedIndices}
                  onUpdate={handleBatchUpdate}
                  onClearSelection={() => setBatchSelectedIndices(new Set())}
                />
              )}

              {/* Scene list */}
              <div className="se-scene-list">
                {filteredScenes.map(({ scene, originalIndex }) => (
                  <SceneCard
                    key={scene.sceneId}
                    scene={scene}
                    index={originalIndex}
                    totalScenes={scenes.length}
                    isExpanded={expandedIndex === originalIndex}
                    isSelected={expandedIndex === originalIndex}
                    isBatchSelected={batchSelectedIndices.has(originalIndex)}
                    validationIssues={validationIssues.filter((i) => i.sceneIndex === originalIndex)}
                    onToggleExpand={() =>
                      setExpandedIndex(expandedIndex === originalIndex ? null : originalIndex)
                    }
                    onUpdate={(updates) => handleUpdateScene(originalIndex, updates)}
                    onToggleLock={() => handleToggleLock(originalIndex)}
                    onToggleBatchSelect={() => handleToggleBatchSelect(originalIndex)}
                    onMoveUp={() => handleMoveUp(originalIndex)}
                    onMoveDown={() => handleMoveDown(originalIndex)}
                    onDelete={() => handleDelete(originalIndex)}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
