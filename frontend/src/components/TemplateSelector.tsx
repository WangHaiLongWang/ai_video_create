import React, { useState, useEffect, useMemo } from 'react'
import { useStudioStore } from '../store'
import * as api from '../api'
import type { CallEstimate, WorkflowSpec } from '../types'
import { computeCallEstimate, applyOverridesToSpec } from '../utils/callEstimate'

interface Props {
  onSelect: (templateId: string) => void
  onClose: () => void
}

export default function TemplateSelector({ onSelect, onClose }: Props) {
  const [templates, setTemplates] = useState<api.TemplateSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  // Template detail (loaded when user selects a template)
  const [selectedTemplate, setSelectedTemplate] = useState<api.TemplateSummary | null>(null)
  const [previewSpec, setPreviewSpec] = useState<WorkflowSpec | null>(null)

  // Parameter overrides
  const [variantCount, setVariantCount] = useState(1)
  const [videoDuration, setVideoDuration] = useState(5)
  const [imageProvider, setImageProvider] = useState('')
  const [videoProvider, setVideoProvider] = useState('')

  const { setWorkflow } = useStudioStore()

  useEffect(() => {
    loadTemplates()
  }, [])

  const loadTemplates = async () => {
    try {
      const result = await api.listTemplates()
      setTemplates(result)
    } catch (e) {
      console.error('Failed to load templates', e)
    } finally {
      setLoading(false)
    }
  }

  const filtered = templates.filter(
    (t) =>
      t.name.includes(search) ||
      t.description.includes(search)
  )

  const handleSelect = async (templateId: string) => {
    setLoading(true)
    try {
      const result = await api.createFromTemplate(templateId, {
        name: '从模板创建',
        prompt: '',
      })
      setSelectedTemplate(templates.find(t => t.id === templateId) ?? null)
      setPreviewSpec(result as unknown as WorkflowSpec)

      // Initialize overrides from template's default values
      const estimate = computeCallEstimate(result as unknown as WorkflowSpec)
      setVariantCount(estimate.variantCount)
      setVideoDuration(estimate.videoDuration)
      setImageProvider(estimate.imageProvider)
      setVideoProvider(estimate.videoProvider)
    } catch (e) {
      console.error('Failed to create from template:', e)
    } finally {
      setLoading(false)
    }
  }

  // Compute call estimate with current overrides
  const callEstimate: CallEstimate | null = useMemo(() => {
    if (!previewSpec) return null
    return computeCallEstimate(previewSpec, { variantCount, videoDuration, imageProvider, videoProvider })
  }, [previewSpec, variantCount, videoDuration, imageProvider, videoProvider])

  // Apply with overrides and confirm
  const handleConfirm = () => {
    if (!previewSpec) return
    const finalSpec = applyOverridesToSpec(previewSpec, { variantCount, videoDuration, imageProvider, videoProvider })
    setWorkflow(finalSpec)
    onSelect(selectedTemplate?.id ?? '')
    onClose()
  }

  const handleBack = () => {
    setSelectedTemplate(null)
    setPreviewSpec(null)
  }

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.panel} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h2 style={styles.title}>选择模板</h2>
          <button style={styles.closeBtn} onClick={onClose}>x</button>
        </div>

        {/* Search bar — only show in template list mode */}
        {!selectedTemplate && (
          <div style={styles.searchBar}>
            <input
              style={styles.searchInput}
              placeholder="搜索模板..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        )}

        <div style={styles.content}>
          {loading ? (
            <div style={styles.loading}>加载中...</div>
          ) : selectedTemplate && previewSpec && callEstimate ? (
            /* ---- Template Preview: Parameters + Cost Estimate ---- */
            <div style={styles.previewContainer}>
              {/* Header */}
              <div style={styles.previewHeader}>
                <button style={styles.backBtn} onClick={handleBack}>&#8592; 返回</button>
                <strong style={styles.previewTitle}>{selectedTemplate.name}</strong>
              </div>

              {/* Call Estimate Summary */}
              <div style={styles.estimateSection}>
                <div style={styles.estimateTitle}>预计调用量</div>
                <div style={styles.estimateGrid}>
                  <div style={styles.estimateItem}>
                    <span style={styles.estimateValue}>{callEstimate.sceneCount}</span>
                    <span style={styles.estimateLabel}>场景</span>
                  </div>
                  <div style={styles.estimateItem}>
                    <span style={styles.estimateValue}>{callEstimate.variantCount}</span>
                    <span style={styles.estimateLabel}>变体/场景</span>
                  </div>
                  <div style={styles.estimateItem}>
                    <span style={styles.estimateValue}>{callEstimate.imageCalls}</span>
                    <span style={styles.estimateLabel}>图片调用</span>
                  </div>
                  <div style={styles.estimateItem}>
                    <span style={styles.estimateValue}>{callEstimate.videoCalls}</span>
                    <span style={styles.estimateLabel}>视频调用</span>
                  </div>
                  <div style={styles.estimateItem}>
                    <span style={styles.estimateValue}>{formatDuration(callEstimate.estimatedDurationSeconds)}</span>
                    <span style={styles.estimateLabel}>预计时长</span>
                  </div>
                </div>
                <div style={styles.estimateDetail}>
                  {callEstimate.sceneCount} 个场景 x {callEstimate.variantCount} 个变体 = {callEstimate.imageCalls} 张图片
                </div>
                <div style={styles.estimateDetail}>
                  预计生成 {callEstimate.videoCalls} 个视频，总时长 {formatDuration(callEstimate.estimatedDurationSeconds)}
                </div>
              </div>

              {/* Parameter Editing */}
              <div style={styles.paramsSection}>
                <div style={styles.paramTitle}>模板参数</div>

                <div style={styles.paramRow}>
                  <label style={styles.paramLabel}>变体数量 (每场景生成图片数)</label>
                  <input
                    style={styles.paramInput}
                    type="number"
                    min={1}
                    max={10}
                    value={variantCount}
                    onChange={(e) => setVariantCount(Math.max(1, Math.min(10, parseInt(e.target.value) || 1)))}
                  />
                </div>

                <div style={styles.paramRow}>
                  <label style={styles.paramLabel}>视频时长 (秒/片段)</label>
                  <input
                    style={styles.paramInput}
                    type="number"
                    min={1}
                    max={60}
                    value={videoDuration}
                    onChange={(e) => setVideoDuration(Math.max(1, Math.min(60, parseInt(e.target.value) || 1)))}
                  />
                </div>

                <div style={styles.paramRow}>
                  <label style={styles.paramLabel}>图片生成 Provider</label>
                  <input
                    style={styles.paramInput}
                    type="text"
                    placeholder="留空使用默认"
                    value={imageProvider}
                    onChange={(e) => setImageProvider(e.target.value)}
                  />
                </div>

                <div style={styles.paramRow}>
                  <label style={styles.paramLabel}>视频生成 Provider</label>
                  <input
                    style={styles.paramInput}
                    type="text"
                    placeholder="留空使用默认"
                    value={videoProvider}
                    onChange={(e) => setVideoProvider(e.target.value)}
                  />
                </div>
              </div>

              {/* Confirm Button */}
              <div style={styles.confirmSection}>
                <button style={styles.confirmBtn} onClick={handleConfirm}>
                  应用模板 ({callEstimate.imageCalls} 图 + {callEstimate.videoCalls} 视频)
                </button>
              </div>
            </div>
          ) : filtered.length === 0 ? (
            <div style={styles.empty}>未找到匹配的模板</div>
          ) : (
            /* ---- Template List ---- */
            filtered.map((t) => (
              <div key={t.id} style={styles.card} onClick={() => handleSelect(t.id)}>
                <div style={styles.cardHeader}>
                  <strong style={styles.cardTitle}>{t.name}</strong>
                  <span style={styles.nodeCount}>{t.node_count} 节点</span>
                </div>
                <p style={styles.cardDesc}>{t.description}</p>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s}s`
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center',
    justifyContent: 'center', zIndex: 1000,
  },
  panel: {
    background: '#1e1e2e', borderRadius: 12, width: 520, maxHeight: '80vh',
    display: 'flex', flexDirection: 'column', border: '1px solid #444',
  },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '16px 20px', borderBottom: '1px solid #333',
  },
  title: { margin: 0, fontSize: 18, color: '#e0e0e0' },
  closeBtn: {
    background: 'none', border: 'none', color: '#888', fontSize: 24, cursor: 'pointer',
  },
  searchBar: { padding: '12px 20px', borderBottom: '1px solid #333' },
  searchInput: {
    width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #444',
    background: '#2a2a3a', color: '#e0e0e0', fontSize: 14, boxSizing: 'border-box',
  },
  content: { flex: 1, overflow: 'auto', padding: 16 },
  card: {
    padding: 16, borderRadius: 8, border: '1px solid #333', marginBottom: 12,
    cursor: 'pointer', transition: 'border-color 0.2s',
  },
  cardHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: 8,
  },
  cardTitle: { fontSize: 15, color: '#e0e0e0' },
  nodeCount: { fontSize: 12, color: '#888' },
  cardDesc: { fontSize: 13, color: '#aaa', margin: '0 0 8px 0' },
  loading: { padding: 40, textAlign: 'center', color: '#888' },
  empty: { padding: 40, textAlign: 'center', color: '#666' },

  /* Preview mode styles */
  previewContainer: { display: 'flex', flexDirection: 'column', gap: 16 },
  previewHeader: {
    display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4,
  },
  backBtn: {
    background: '#2a2a3a', border: '1px solid #444', borderRadius: 6,
    color: '#aaa', fontSize: 13, padding: '4px 10px', cursor: 'pointer',
  },
  previewTitle: { fontSize: 16, color: '#e0e0e0' },

  /* Estimate section */
  estimateSection: {
    background: '#15171a', borderRadius: 8, padding: 14, border: '1px solid #333',
  },
  estimateTitle: {
    fontSize: 12, fontWeight: 600, color: '#aaa', textTransform: 'uppercase' as const,
    letterSpacing: 0.5, marginBottom: 10,
  },
  estimateGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6,
    marginBottom: 10,
  },
  estimateItem: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    padding: '6px 4px', borderRadius: 5, background: '#1b1e1a',
  },
  estimateValue: {
    fontSize: 14, fontWeight: 700, color: '#7dce7d',
    fontFamily: '"Cascadia Code", monospace',
  },
  estimateLabel: { fontSize: 9, color: '#5a6055', marginTop: 2 },
  estimateDetail: {
    fontSize: 11, color: '#737a6e', lineHeight: '18px',
  },

  /* Parameter section */
  paramsSection: {
    background: '#15171a', borderRadius: 8, padding: 14, border: '1px solid #333',
  },
  paramTitle: {
    fontSize: 12, fontWeight: 600, color: '#aaa', textTransform: 'uppercase' as const,
    letterSpacing: 0.5, marginBottom: 10,
  },
  paramRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: 10,
  },
  paramLabel: {
    fontSize: 12, color: '#aaa',
  },
  paramInput: {
    width: 120, padding: '6px 10px', borderRadius: 6, border: '1px solid #444',
    background: '#2a2a3a', color: '#e0e0e0', fontSize: 13, textAlign: 'right' as const,
    boxSizing: 'border-box',
  },

  /* Confirm section */
  confirmSection: {
    display: 'flex', justifyContent: 'flex-end', marginTop: 4,
  },
  confirmBtn: {
    padding: '10px 20px', borderRadius: 7, border: 'none',
    background: '#7dce7d', color: '#0a0f0a', fontSize: 13,
    fontWeight: 600, cursor: 'pointer', transition: 'opacity 0.2s',
  },
}
