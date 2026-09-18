/**
 * ImportDialog — 导入 Scene Bundle
 *
 * 文件选择 (.json/.csv/.txt)、预览（首场景标题、场景数量）、确认导入。
 */

import { useState, useRef } from 'react'
import { FileArrowUp, Warning, X } from '@phosphor-icons/react'
import { importSceneBundle } from '../api'
import type { ScenePromptBundle } from '../schemas/scene-bundle'

const ACCEPTED_TYPES = '.json,.csv,.txt'

export interface ImportDialogProps {
  workflowId: string
  onClose: () => void
  onImported: () => void  // called after successful import so parent can refresh
}

interface Preview {
  title: string
  sceneCount: number
  raw: Record<string, unknown>
}

function parseImportedFile(text: string, filename: string): Preview {
  const ext = filename.split('.').pop()?.toLowerCase()

  if (ext === 'json' || ext === 'jsonl') {
    // Try parsing as a full bundle first
    const parsed = JSON.parse(text) as Record<string, unknown>
    if (parsed && typeof parsed === 'object' && Array.isArray(parsed.scenes)) {
      const bundle = parsed as unknown as ScenePromptBundle
      return {
        title: bundle.title || '(无标题)',
        sceneCount: bundle.scenes.length,
        raw: parsed,
      }
    }
    throw new Error('无效的 JSON 格式：缺少 scenes 数组')
  }

  // For CSV / TXT, wrap content as a simple bundle for preview
  const lines = text.split('\n').filter((l) => l.trim())
  return {
    title: filename.replace(/\.[^.]+$/, ''),
    sceneCount: lines.length,
    raw: {
      schemaVersion: '1.0',
      storyboardId: '',
      workflowId: '',
      executionId: '',
      title: filename.replace(/\.[^.]+$/, ''),
      scenes: [],
    },
  }
}

export function ImportDialog({ workflowId, onClose, onImported }: ImportDialogProps) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [fileText, setFileText] = useState<string | null>(null)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fileName, setFileName] = useState<string>('')

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    setError(null)
    setPreview(null)
    setFileText(null)
    setFileName(file.name)

    const reader = new FileReader()
    reader.onload = () => {
      const text = reader.result as string
      try {
        const p = parseImportedFile(text, file.name)
        setPreview(p)
        setFileText(text)
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : '解析文件失败'
        setError(msg)
      }
    }
    reader.onerror = () => setError('读取文件失败')
    reader.readAsText(file)
  }

  async function handleImport() {
    if (!preview?.raw) return
    setImporting(true)
    setError(null)

    try {
      await importSceneBundle(workflowId, preview.raw)
      onImported()
      onClose()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '导入失败'
      setError(msg)
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="field-dialog-overlay" onClick={onClose}>
      <div className="field-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="export-dialog-header">
          <h3><FileArrowUp size={16} /> 导入 Scene Bundle</h3>
          <button className="export-dialog-close" onClick={onClose} aria-label="关闭">
            <X size={16} />
          </button>
        </div>

        {error && (
          <div className="export-dialog-error">
            <Warning size={14} /> {error}
          </div>
        )}

        <label>
          <span>选择文件</span>
          <input
            ref={fileRef}
            type="file"
            accept={ACCEPTED_TYPES}
            onChange={handleFileChange}
            className="import-file-input"
          />
        </label>

        {fileName && (
          <div className="import-file-info">
            <span className="import-file-name">{fileName}</span>
          </div>
        )}

        {preview && (
          <div className="import-preview">
            <div className="import-preview-title">{preview.title}</div>
            <div className="import-preview-count">{preview.sceneCount} 个场景</div>
          </div>
        )}

        <div className="field-dialog-actions">
          <button className="field-dialog-cancel" onClick={onClose}>取消</button>
          <button
            className="field-dialog-save"
            onClick={handleImport}
            disabled={importing || !preview}
          >
            {importing ? '导入中...' : '确认导入'}
          </button>
        </div>
      </div>
    </div>
  )
}
