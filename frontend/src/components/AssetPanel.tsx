/**
 * AssetPanel — 资产管理面板
 *
 * 显示当前执行产生的资产（图片、视频等），
 * 支持按类型筛选、预览、下载和删除。
 */

import { useState, useEffect, useCallback } from 'react'
import {
  X,
  Download,
  Trash,
  Eye,
  FileVideo,
  FileAudio,
  FileText,
  FileImage,
  Folder,
} from '@phosphor-icons/react'
import { listAssets, deleteAsset, getAssetDownloadUrl, type AssetInfo } from '../api'
import { useExecutionStore } from '../stores/executionStore'

// ==================== 类型定义 ====================

type AssetKind = 'all' | 'image' | 'video' | 'audio' | 'text'

interface Props {
  onClose: () => void
}

// ==================== 工具函数 ====================

/** 格式化文件大小 */
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

/** 格式化日期 */
function formatDate(isoStr: string): string {
  try {
    const d = new Date(isoStr)
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return isoStr
  }
}

/** 根据 asset_type 或 mime_type 判断 kind */
function getAssetKind(asset: AssetInfo): string {
  const mime = asset.mime_type?.toLowerCase() ?? ''
  const type = asset.asset_type?.toLowerCase() ?? ''
  if (type === 'image' || mime.startsWith('image/')) return 'image'
  if (type === 'video' || mime.startsWith('video/')) return 'video'
  if (type === 'audio' || mime.startsWith('audio/')) return 'audio'
  if (type === 'text' || mime.startsWith('text/')) return 'text'
  return type || 'unknown'
}

/** 从路径提取文件名 */
function getFileName(path: string): string {
  if (!path) return '未知文件'
  const parts = path.replace(/\\/g, '/').split('/')
  return parts[parts.length - 1] || path
}

/** 获取 kind 对应的图标 */
function KindIcon({ kind }: { kind: string }) {
  switch (kind) {
    case 'image': return <FileImage size={20} weight="fill" />
    case 'video': return <FileVideo size={20} weight="fill" />
    case 'audio': return <FileAudio size={20} weight="fill" />
    case 'text': return <FileText size={20} weight="fill" />
    default: return <Folder size={20} weight="fill" />
  }
}

// ==================== 预览弹窗 ====================

function PreviewModal({
  asset,
  onClose,
}: {
  asset: AssetInfo
  onClose: () => void
}) {
  const kind = getAssetKind(asset)
  const downloadUrl = getAssetDownloadUrl(asset.id)

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    },
    [onClose],
  )

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  return (
    <div className="asset-preview-overlay" onClick={onClose}>
      <div className="asset-preview-modal" onClick={(e) => e.stopPropagation()}>
        <div className="asset-preview-header">
          <span className="asset-preview-title">{getFileName(asset.file_path)}</span>
          <button className="asset-preview-close" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </div>
        <div className="asset-preview-body">
          {kind === 'image' && (
            <img
              src={downloadUrl}
              alt={getFileName(asset.file_path)}
              className="asset-preview-image"
            />
          )}
          {kind === 'video' && (
            <video
              src={downloadUrl}
              controls
              className="asset-preview-video"
            />
          )}
          {kind === 'audio' && (
            <audio src={downloadUrl} controls className="asset-preview-audio" />
          )}
          {(kind === 'text' || kind === 'unknown') && (
            <div className="asset-preview-generic">
              <KindIcon kind={kind} />
              <p>无法预览此类型的文件</p>
            </div>
          )}
        </div>
        <div className="asset-preview-footer">
          <a
            href={downloadUrl}
            download
            className="asset-action-btn"
            target="_blank"
            rel="noopener noreferrer"
          >
            <Download size={14} /> 下载
          </a>
          <span className="asset-preview-info">
            {formatFileSize(asset.file_size)} · {asset.mime_type}
          </span>
        </div>
      </div>
    </div>
  )
}

// ==================== 资产卡片 ====================

function AssetCard({
  asset,
  onPreview,
  onDownload,
  onDelete,
}: {
  asset: AssetInfo
  onPreview: (asset: AssetInfo) => void
  onDownload: (asset: AssetInfo) => void
  onDelete: (asset: AssetInfo) => void
}) {
  const kind = getAssetKind(asset)
  const downloadUrl = getAssetDownloadUrl(asset.id)

  return (
    <div className={`asset-card asset-card--${kind}`}>
      <div className="asset-card-thumb" onClick={() => onPreview(asset)}>
        {kind === 'image' ? (
          <img src={downloadUrl} alt={getFileName(asset.file_path)} />
        ) : (
          <div className="asset-card-icon">
            <KindIcon kind={kind} />
          </div>
        )}
      </div>
      <div className="asset-card-info">
        <span className="asset-card-name" title={getFileName(asset.file_path)}>
          {getFileName(asset.file_path)}
        </span>
        <span className="asset-card-meta">
          {formatFileSize(asset.file_size)} · {formatDate(asset.created_at)}
        </span>
      </div>
      <div className="asset-card-actions">
        <button
          className="asset-card-action"
          onClick={() => onPreview(asset)}
          title="预览"
          aria-label="预览"
        >
          <Eye size={14} />
        </button>
        <a
          href={downloadUrl}
          download
          className="asset-card-action"
          title="下载"
          aria-label="下载"
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => {
            e.preventDefault()
            onDownload(asset)
          }}
        >
          <Download size={14} />
        </a>
        <button
          className="asset-card-action asset-card-action--danger"
          onClick={() => onDelete(asset)}
          title="删除"
          aria-label="删除"
        >
          <Trash size={14} />
        </button>
      </div>
    </div>
  )
}

// ==================== 主组件 ====================

export function AssetPanel({ onClose }: Props) {
  const executionId = useExecutionStore((s) => s.executionId)

  const [assets, setAssets] = useState<AssetInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState<AssetKind>('all')
  const [previewAsset, setPreviewAsset] = useState<AssetInfo | null>(null)

  /** 加载资产列表 */
  const loadAssets = useCallback(async () => {
    setLoading(true)
    try {
      const params: { execution_id?: string; asset_type?: string } = {}
      if (executionId) params.execution_id = executionId
      if (filter !== 'all') params.asset_type = filter
      const result = await listAssets(params)
      setAssets(result)
    } catch (err) {
      console.error('加载资产失败:', err)
    } finally {
      setLoading(false)
    }
  }, [executionId, filter])

  useEffect(() => {
    loadAssets()
  }, [loadAssets])

  /** 下载资产 */
  const handleDownload = useCallback((asset: AssetInfo) => {
    const url = getAssetDownloadUrl(asset.id)
    const a = document.createElement('a')
    a.href = url
    a.download = getFileName(asset.file_path)
    a.target = '_blank'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }, [])

  /** 删除资产 */
  const handleDelete = useCallback(
    async (asset: AssetInfo) => {
      if (!window.confirm(`确定删除资产 "${getFileName(asset.file_path)}" 吗？`)) return
      try {
        await deleteAsset(asset.id)
        setAssets((prev) => prev.filter((a) => a.id !== asset.id))
      } catch (err) {
        console.error('删除资产失败:', err)
        alert('删除失败，请稍后重试')
      }
    },
    [],
  )

  /** 筛选后的资产列表 */
  const filteredAssets = filter === 'all'
    ? assets
    : assets.filter((a) => getAssetKind(a) === filter)

  /** 各类型数量统计 */
  const counts = {
    all: assets.length,
    image: assets.filter((a) => getAssetKind(a) === 'image').length,
    video: assets.filter((a) => getAssetKind(a) === 'video').length,
    audio: assets.filter((a) => getAssetKind(a) === 'audio').length,
    text: assets.filter((a) => getAssetKind(a) === 'text').length,
  }

  const filters: { key: AssetKind; label: string }[] = [
    { key: 'all', label: '全部' },
    { key: 'image', label: '图片' },
    { key: 'video', label: '视频' },
    { key: 'audio', label: '音频' },
    { key: 'text', label: '文本' },
  ]

  return (
    <>
      <div className="asset-panel-overlay" onClick={onClose}>
        <div className="asset-panel" onClick={(e) => e.stopPropagation()}>
          {/* 头部 */}
          <div className="asset-panel-header">
            <div className="asset-panel-title">
              <Folder size={16} weight="fill" />
              资产管理
            </div>
            <button className="asset-panel-close" onClick={onClose} aria-label="关闭">
              <X size={18} />
            </button>
          </div>

          {/* 筛选标签 */}
          <div className="asset-filter-bar">
            {filters.map((f) => (
              <button
                key={f.key}
                className={`asset-filter-btn ${filter === f.key ? 'asset-filter-btn--active' : ''}`}
                onClick={() => setFilter(f.key)}
              >
                {f.label}
                {counts[f.key] > 0 && (
                  <span className="asset-filter-count">{counts[f.key]}</span>
                )}
              </button>
            ))}
          </div>

          {/* 内容区域 */}
          <div className="asset-panel-body">
            {loading && (
              <div className="asset-panel-empty">
                <p>加载中...</p>
              </div>
            )}

            {!loading && filteredAssets.length === 0 && (
              <div className="asset-panel-empty">
                <Folder size={40} />
                <strong>暂无资产</strong>
                <p>
                  {executionId
                    ? '当前执行尚未产生资产'
                    : '请先执行工作流以生成资产'}
                </p>
              </div>
            )}

            {!loading && filteredAssets.length > 0 && (
              <div className="asset-grid">
                {filteredAssets.map((asset) => (
                  <AssetCard
                    key={asset.id}
                    asset={asset}
                    onPreview={setPreviewAsset}
                    onDownload={handleDownload}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 预览弹窗 */}
      {previewAsset && (
        <PreviewModal
          asset={previewAsset}
          onClose={() => setPreviewAsset(null)}
        />
      )}
    </>
  )
}
