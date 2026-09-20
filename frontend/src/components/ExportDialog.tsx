/**
 * ExportDialog — 导出 Scene Bundle
 *
 * 选择来源 (draft/execution/merged)、格式 (JSON/Markdown/CSV/Text/Qwen JSONL/Wan3 JSONL)，
 * 预览文件名，点击导出按钮触发浏览器下载。
 */

import { useState, useEffect } from 'react'
import { Export, Download, Warning, X } from '@phosphor-icons/react'
import {
  listSceneDrafts,
  exportSceneBundle,
  type SceneDraftSummary,
  type ExportFormat,
} from '../api'

const FORMAT_OPTIONS: { value: ExportFormat; label: string; ext: string }[] = [
  { value: 'json', label: 'JSON', ext: 'json' },
  { value: 'markdown', label: 'Markdown', ext: 'md' },
  { value: 'csv', label: 'CSV', ext: 'csv' },
  { value: 'text', label: 'Text', ext: 'txt' },
  { value: 'qwen_jsonl', label: 'Qwen JSONL', ext: 'jsonl' },
  { value: 'wan3_jsonl', label: 'Wan3 JSONL', ext: 'jsonl' },
]

const SOURCE_OPTIONS: { value: string; label: string }[] = [
  { value: 'draft', label: '草稿' },
  { value: 'execution', label: '执行结果' },
  { value: 'merged', label: '合并结果' },
]

function getFilename(source: string, format: ExportFormat): string {
  const suffix = source === 'draft' ? '' : `-${source}`
  const ext = FORMAT_OPTIONS.find((f) => f.value === format)?.ext ?? 'txt'
  return `scene-bundle${suffix}.${ext}`
}

export interface ExportDialogProps {
  workflowId: string
  onClose: () => void
}

export function ExportDialog({ workflowId, onClose }: ExportDialogProps) {
  const [drafts, setDrafts] = useState<SceneDraftSummary[]>([])
  const [loadingDrafts, setLoadingDrafts] = useState(true)
  const [selectedDraft, setSelectedDraft] = useState<string>('')
  const [source, setSource] = useState<string>('draft')
  const [format, setFormat] = useState<ExportFormat>('json')
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoadingDrafts(true)
    listSceneDrafts(workflowId)
      .then((list) => {
        if (cancelled) return
        setDrafts(list)
        if (list.length > 0) {
          setSelectedDraft(list[0].draft_id)
        }
        setLoadingDrafts(false)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err.message || '加载草稿列表失败')
        setLoadingDrafts(false)
      })
    return () => { cancelled = true }
  }, [workflowId])

  const filename = getFilename(source, format)

  async function handleExport() {
    if (!selectedDraft) return
    setExporting(true)
    setError(null)

    try {
      const res = await exportSceneBundle(selectedDraft, format)
      const blob = new Blob([res.content], {
        type: format === 'json' ? 'application/json' : 'text/plain; charset=utf-8',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      onClose()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '导出失败'
      setError(msg)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="field-dialog-overlay" onClick={onClose}>
      <div className="field-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="export-dialog-header">
          <h3><Export size={16} /> 导出 Scene Bundle</h3>
          <button className="export-dialog-close" onClick={onClose} aria-label="关闭">
            <X size={16} />
          </button>
        </div>

        {error && (
          <div className="export-dialog-error">
            <Warning size={14} /> {error}
          </div>
        )}

        {loadingDrafts && (
          <div className="export-dialog-loading">加载中...</div>
        )}

        {!loadingDrafts && drafts.length === 0 && (
          <div className="export-dialog-empty">没有可用的 Scene 草稿</div>
        )}

        {!loadingDrafts && drafts.length > 0 && (
          <label>
            <span>选择草稿</span>
            <select
              value={selectedDraft}
              onChange={(e) => setSelectedDraft(e.target.value)}
            >
              {drafts.map((d) => (
                <option key={d.draft_id} value={d.draft_id}>
                  {d.name} ({d.scene_count} 场景)
                </option>
              ))}
            </select>
          </label>
        )}

        <label>
          <span>来源</span>
          <div className="export-radio-group">
            {SOURCE_OPTIONS.map((opt) => (
              <label key={opt.value} className="export-radio-item">
                <input
                  type="radio"
                  name="source"
                  value={opt.value}
                  checked={source === opt.value}
                  onChange={(e) => setSource(e.target.value)}
                />
                <span>{opt.label}</span>
              </label>
            ))}
          </div>
        </label>

        <label>
          <span>格式</span>
          <div className="export-radio-group">
            {FORMAT_OPTIONS.map((opt) => (
              <label key={opt.value} className="export-radio-item">
                <input
                  type="radio"
                  name="format"
                  value={opt.value}
                  checked={format === opt.value}
                  onChange={(e) => setFormat(e.target.value as ExportFormat)}
                />
                <span>{opt.label}</span>
              </label>
            ))}
          </div>
        </label>

        <label>
          <span>文件名</span>
          <input type="text" value={filename} readOnly className="export-filename" />
        </label>

        <div className="field-dialog-actions">
          <button className="field-dialog-cancel" onClick={onClose}>取消</button>
          <button
            className="field-dialog-save"
            onClick={handleExport}
            disabled={exporting || !selectedDraft || loadingDrafts}
          >
            {exporting ? (
              <>导出中...</>
            ) : (
              <><Download size={14} /> 导出</>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
