/**
 * WorkflowListPage -- 工作流列表页 (模态覆盖层)
 *
 * 功能:
 * - 列出所有已保存的工作流
 * - 每个工作流显示: 名称、节点数量、最后修改时间
 * - 操作: 加载、删除、导出 (下载 JSON)
 * - 导入按钮: 打开文件选择器导入 JSON
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { List, Download, Trash, Upload, MagnifyingGlass, ArrowClockwise, CaretRight, FileJs } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import * as api from '../api'

interface Props {
  onClose: () => void
}

export default function WorkflowListPage({ onClose }: Props) {
  const [workflows, setWorkflows] = useState<api.WorkflowSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { setWorkflow } = useStudioStore()

  const loadWorkflows = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const list = await api.fetchWorkflows()
      setWorkflows(list)
    } catch (e) {
      console.error('Failed to load workflows:', e)
      setError('加载工作流列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadWorkflows()
  }, [loadWorkflows])

  const filtered = workflows.filter(
    (w) =>
      w.name.toLowerCase().includes(search.toLowerCase()) ||
      w.description?.toLowerCase().includes(search.toLowerCase()),
  )

  /** 加载工作流到画布 */
  const handleLoad = async (id: string) => {
    try {
      const detail = await api.getWorkflow(id)
      const spec = detail.spec as unknown as ReturnType<typeof useStudioStore.getState>['workflow']
      setWorkflow(spec)
      onClose()
    } catch (e) {
      console.error('Failed to load workflow:', e)
      setError('加载工作流失败')
    }
  }

  /** 删除工作流 */
  const handleDelete = async (id: string) => {
    setDeleting(true)
    try {
      await api.deleteWorkflow(id)
      setWorkflows((prev) => prev.filter((w) => w.id !== id))
      setConfirmDeleteId(null)
    } catch (e) {
      console.error('Failed to delete workflow:', e)
      setError('删除工作流失败')
    } finally {
      setDeleting(false)
    }
  }

  /** 导出工作流为 JSON 文件 */
  const handleExport = async (id: string, name: string) => {
    try {
      const result = await api.exportWorkflow(id)
      const json = JSON.stringify(result.spec, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${name || 'workflow'}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('Failed to export workflow:', e)
      setError('导出工作流失败')
    }
  }

  /** 处理文件导入 */
  const handleFileImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setImporting(true)
    setError('')
    try {
      const text = await file.text()
      const spec = JSON.parse(text) as Record<string, unknown>
      await api.importWorkflow(spec)
      // 刷新列表
      await loadWorkflows()
    } catch (e) {
      console.error('Failed to import workflow:', e)
      setError('导入工作流失败: ' + (e instanceof Error ? e.message : '未知错误'))
    } finally {
      setImporting(false)
      // 重置 input 以便可以再次选择同一文件
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  /** 格式化日期显示 */
  const formatDate = (dateStr: string): string => {
    try {
      const d = new Date(dateStr)
      const now = new Date()
      const diff = now.getTime() - d.getTime()
      const minutes = Math.floor(diff / 60000)
      const hours = Math.floor(diff / 3600000)
      const days = Math.floor(diff / 86400000)

      if (minutes < 1) return '刚刚'
      if (minutes < 60) return `${minutes} 分钟前`
      if (hours < 24) return `${hours} 小时前`
      if (days < 30) return `${days} 天前`
      return d.toLocaleDateString('zh-CN')
    } catch {
      return dateStr
    }
  }

  return (
    <div className="wf-overlay" onClick={onClose}>
      <div className="wf-panel" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="wf-header">
          <div className="wf-header-left">
            <List size={20} weight="fill" />
            <h2>工作流列表</h2>
          </div>
          <button className="wf-close-btn" onClick={onClose}>&times;</button>
        </div>

        {/* Toolbar */}
        <div className="wf-toolbar">
          <div className="wf-search">
            <MagnifyingGlass size={14} />
            <input
              placeholder="搜索工作流..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="wf-toolbar-actions">
            <button
              className="wf-tool-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={importing}
            >
              <Upload size={14} />
              {importing ? '导入中...' : '导入'}
            </button>
            <button className="wf-tool-btn" onClick={loadWorkflows}>
              <ArrowClockwise size={14} />
              刷新
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            style={{ display: 'none' }}
            onChange={handleFileImport}
          />
        </div>

        {/* Error */}
        {error && (
          <div className="wf-error">{error}</div>
        )}

        {/* Content */}
        <div className="wf-content">
          {loading ? (
            <div className="wf-loading">加载中...</div>
          ) : filtered.length === 0 ? (
            <div className="wf-empty">
              <FileJs size={48} />
              <strong>暂无工作流</strong>
              <p>{search ? '没有找到匹配的工作流' : '开始创建你的第一个工作流吧'}</p>
            </div>
          ) : (
            <div className="wf-list">
              {filtered.map((w) => (
                <div key={w.id} className="wf-card">
                  <div className="wf-card-main" onClick={() => handleLoad(w.id)}>
                    <div className="wf-card-info">
                      <strong className="wf-card-name">{w.name}</strong>
                      <div className="wf-card-meta">
                        <span className="wf-card-desc">{w.description || '无描述'}</span>
                        <span className="wf-card-detail">
                          {w.version !== undefined && <span>v{w.version}</span>}
                          <span>{formatDate(w.updated_at)}</span>
                        </span>
                      </div>
                    </div>
                    <CaretRight size={16} className="wf-card-arrow" />
                  </div>
                  <div className="wf-card-actions">
                    <button
                      className="wf-action-btn wf-action-load"
                      onClick={() => handleLoad(w.id)}
                      title="加载到画布"
                    >
                      <CaretRight size={13} />
                      加载
                    </button>
                    <button
                      className="wf-action-btn wf-action-export"
                      onClick={() => handleExport(w.id, w.name)}
                      title="导出为 JSON"
                    >
                      <Download size={13} />
                      导出
                    </button>
                    {confirmDeleteId === w.id ? (
                      <div className="wf-confirm-delete">
                        <span>确认删除?</span>
                        <button
                          className="wf-action-btn wf-action-confirm"
                          onClick={() => handleDelete(w.id)}
                          disabled={deleting}
                        >
                          {deleting ? '...' : '是'}
                        </button>
                        <button
                          className="wf-action-btn wf-action-cancel"
                          onClick={() => setConfirmDeleteId(null)}
                        >
                          否
                        </button>
                      </div>
                    ) : (
                      <button
                        className="wf-action-btn wf-action-delete"
                        onClick={() => setConfirmDeleteId(w.id)}
                        title="删除工作流"
                      >
                        <Trash size={13} />
                        删除
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="wf-footer">
          <span>{workflows.length} 个工作流</span>
        </div>
      </div>
    </div>
  )
}
