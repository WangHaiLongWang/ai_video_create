import React, { useState, useEffect } from 'react';

interface TemplateInfo {
  id: string;
  name: string;
  description: string;
  tags: string[];
  node_count: number;
}

interface Props {
  onSelect: (templateId: string) => void;
  onClose: () => void;
}

export default function TemplateSelector({ onSelect, onClose }: Props) {
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const resp = await fetch('/api/templates');
      if (resp.ok) {
        setTemplates(await resp.json());
      }
    } catch (e) {
      console.error('Failed to load templates', e);
    } finally {
      setLoading(false);
    }
  };

  const filtered = templates.filter(
    (t) =>
      t.name.includes(search) ||
      t.description.includes(search) ||
      t.tags.some((tag) => tag.includes(search))
  );

  const handleSelect = async (templateId: string) => {
    try {
      const resp = await fetch(`/api/templates/${templateId}/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (resp.ok) {
        onSelect(templateId);
        onClose();
      }
    } catch (e) {
      console.error('Failed to create from template', e);
    }
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.panel} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h2 style={styles.title}>📋 选择模板</h2>
          <button style={styles.closeBtn} onClick={onClose}>×</button>
        </div>

        <div style={styles.searchBar}>
          <input
            style={styles.searchInput}
            placeholder="搜索模板..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div style={styles.content}>
          {loading ? (
            <div style={styles.loading}>加载中...</div>
          ) : filtered.length === 0 ? (
            <div style={styles.empty}>未找到匹配的模板</div>
          ) : (
            filtered.map((t) => (
              <div key={t.id} style={styles.card} onClick={() => handleSelect(t.id)}>
                <div style={styles.cardHeader}>
                  <strong style={styles.cardTitle}>{t.name}</strong>
                  <span style={styles.nodeCount}>{t.node_count} 节点</span>
                </div>
                <p style={styles.cardDesc}>{t.description}</p>
                <div style={styles.tags}>
                  {t.tags.map((tag) => (
                    <span key={tag} style={styles.tag}>{tag}</span>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
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
  tags: { display: 'flex', gap: 6, flexWrap: 'wrap' },
  tag: {
    padding: '2px 8px', borderRadius: 4, background: '#333',
    color: '#aaa', fontSize: 11,
  },
  loading: { padding: 40, textAlign: 'center', color: '#888' },
  empty: { padding: 40, textAlign: 'center', color: '#666' },
};
